from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db

router = Router()

DATE_FORMAT = "%Y-%m-%d"
DISPLAY_DATE_FORMAT = "%d.%m.%Y"
DISPLAY_DATETIME_FORMAT = "%d.%m.%Y %H:%M"
TIME_SLOTS = [f"{h:02d}:00" for h in range(9, 20)]
DAYS_AHEAD = 7


class Booking(StatesGroup):
    entering_name = State()


class AdminActions(StatesGroup):
    waiting_master_name = State()


def masters_keyboard(masters):
    builder = InlineKeyboardBuilder()
    for m in masters:
        builder.button(text=m["name"], callback_data=f"master:{m['id']}")
    builder.adjust(1)
    return builder.as_markup()


def dates_keyboard(master_id: int):
    builder = InlineKeyboardBuilder()
    today = datetime.now().date()
    for i in range(DAYS_AHEAD):
        d = today + timedelta(days=i)
        builder.button(
            text=d.strftime(DISPLAY_DATE_FORMAT),
            callback_data=f"date:{master_id}:{d.strftime(DATE_FORMAT)}",
        )
    builder.adjust(2)
    return builder.as_markup()


def times_keyboard(master_id: int, date_str: str):
    builder = InlineKeyboardBuilder()
    for t in TIME_SLOTS:
        builder.button(text=t, callback_data=f"time:{master_id}:{date_str}:{t}")
    builder.adjust(4)
    return builder.as_markup()


def build_router(pool, admin_ids: set[int]) -> Router:

    def is_admin(user_id: int) -> bool:
        return user_id in admin_ids

    @router.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext):
        await state.clear()
        masters = await db.list_masters(pool)
        if not masters:
            await message.answer("Пока нет доступных мастеров. Загляните позже.")
            return
        await message.answer("Выберите мастера:", reply_markup=masters_keyboard(masters))

    @router.callback_query(F.data.startswith("master:"))
    async def cb_choose_master(callback: CallbackQuery):
        master_id = int(callback.data.split(":")[1])
        await callback.message.edit_text("Выберите дату:", reply_markup=dates_keyboard(master_id))
        await callback.answer()

    @router.callback_query(F.data.startswith("date:"))
    async def cb_choose_date(callback: CallbackQuery):
        _, master_id, date_str = callback.data.split(":")
        await callback.message.edit_text(
            "Выберите время:", reply_markup=times_keyboard(int(master_id), date_str)
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("time:"))
    async def cb_choose_time(callback: CallbackQuery, state: FSMContext):
        _, master_id, date_str, time_str = callback.data.split(":", 3)
        booking_dt = datetime.strptime(f"{date_str} {time_str}", f"{DATE_FORMAT} %H:%M")

        if booking_dt < datetime.now():
            await callback.answer("Это время уже прошло, выберите другое.", show_alert=True)
            return

        await state.update_data(master_id=int(master_id), booking_time=booking_dt)
        await state.set_state(Booking.entering_name)
        await callback.message.edit_text("Как вас зовут?")
        await callback.answer()

    @router.message(Booking.entering_name, F.text)
    async def process_name_and_confirm(message: Message, state: FSMContext):
        client_name = message.text.strip()
        data = await state.get_data()
        master_id = data["master_id"]
        booking_time = data["booking_time"]

        booking = await db.create_booking(
            pool,
            master_id=master_id,
            telegram_id=message.from_user.id,
            client_name=client_name,
            booking_time=booking_time,
        )

        if booking is None:
            await state.clear()
            await message.answer(
                "К сожалению, это время уже заняли, пока вы вводили имя.\n"
                "Начните заново: /start"
            )
            return

        await state.clear()
        await message.answer(
            f"Запись подтверждена\n"
            f"Время: {booking_time.strftime(DISPLAY_DATETIME_FORMAT)}\n"
            f"Имя: {client_name}\n\n"
            f"Посмотреть свои записи: /mybookings"
        )

    @router.message(Command("mybookings"))
    async def cmd_my_bookings(message: Message):
        bookings = await db.list_bookings_by_user(pool, message.from_user.id)
        if not bookings:
            await message.answer("У вас пока нет активных записей.")
            return

        text_lines = []
        builder = InlineKeyboardBuilder()
        for b in bookings:
            text_lines.append(
                f"#{b['id']} — {b['master_name']}, "
                f"{b['booking_time'].strftime(DISPLAY_DATETIME_FORMAT)}"
            )
            builder.button(text=f"Отменить #{b['id']}", callback_data=f"cancel_booking:{b['id']}")
        builder.adjust(1)

        await message.answer("Ваши записи:\n" + "\n".join(text_lines), reply_markup=builder.as_markup())

    @router.callback_query(F.data.startswith("cancel_booking:"))
    async def cb_cancel_booking(callback: CallbackQuery):
        booking_id = int(callback.data.split(":")[1])
        cancelled = await db.cancel_booking(pool, booking_id, callback.from_user.id)
        if cancelled is None:
            await callback.answer("Не нашёл такую запись за вами.", show_alert=True)
            return
        await callback.message.edit_text(f"Запись #{booking_id} отменена.")
        await callback.answer()

    @router.message(Command("admin"))
    async def cmd_admin(message: Message):
        if not is_admin(message.from_user.id):
            return
        builder = InlineKeyboardBuilder()
        builder.button(text="📋 Записи", callback_data="admin:bookings")
        builder.button(text="💇 Мастера", callback_data="admin:masters")
        builder.adjust(1)
        await message.answer("Админ-панель:", reply_markup=builder.as_markup())

    @router.callback_query(F.data == "admin:bookings")
    async def cb_admin_bookings(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer()
            return

        bookings = await db.list_all_upcoming_bookings(pool)
        if not bookings:
            await callback.message.edit_text("Активных записей нет.")
            await callback.answer()
            return

        text_lines = []
        builder = InlineKeyboardBuilder()
        for b in bookings:
            text_lines.append(
                f"#{b['id']} — {b['master_name']}, {b['client_name']}, "
                f"{b['booking_time'].strftime(DISPLAY_DATETIME_FORMAT)}"
            )
            builder.button(text=f"#{b['id']}", callback_data=f"admin_cancel:{b['id']}")
        builder.adjust(3)

        await callback.message.edit_text(
            "Все записи:\n" + "\n".join(text_lines), reply_markup=builder.as_markup()
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("admin_cancel:"))
    async def cb_admin_cancel(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer()
            return
        booking_id = int(callback.data.split(":")[1])
        cancelled = await db.admin_cancel_booking(pool, booking_id)
        if cancelled is None:
            await callback.answer("Запись не найдена.", show_alert=True)
            return
        await callback.answer(f"Запись #{booking_id} отменена.", show_alert=True)
        await cb_admin_bookings(callback)

    @router.callback_query(F.data == "admin:masters")
    async def cb_admin_masters(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer()
            return
        masters = await db.list_masters(pool)
        builder = InlineKeyboardBuilder()
        for m in masters:
            builder.button(text=f"{m['name']}", callback_data=f"admin_del_master:{m['id']}")
        builder.button(text="➕ Добавить мастера", callback_data="admin_add_master")
        builder.adjust(1)
        await callback.message.edit_text("Мастера:", reply_markup=builder.as_markup())
        await callback.answer()

    @router.callback_query(F.data == "admin_add_master")
    async def cb_admin_add_master(callback: CallbackQuery, state: FSMContext):
        if not is_admin(callback.from_user.id):
            await callback.answer()
            return
        await state.set_state(AdminActions.waiting_master_name)
        await callback.message.edit_text("Введите имя нового мастера:")
        await callback.answer()

    @router.message(AdminActions.waiting_master_name, F.text)
    async def process_new_master_name(message: Message, state: FSMContext):
        if not is_admin(message.from_user.id):
            return
        name = message.text.strip()
        await db.add_master(pool, name)
        await state.clear()
        await message.answer(f"Мастер «{name}» добавлен")

    @router.callback_query(F.data.startswith("admin_del_master:"))
    async def cb_admin_del_master(callback: CallbackQuery):
        if not is_admin(callback.from_user.id):
            await callback.answer()
            return
        master_id = int(callback.data.split(":")[1])
        deleted = await db.delete_master(pool, master_id)
        if not deleted:
            await callback.answer("Нельзя удалить: у мастера есть записи.", show_alert=True)
            return
        await callback.answer("Мастер удалён.", show_alert=True)
        await cb_admin_masters(callback)

    return router


def create_dispatcher(pool, admin_ids: set[int]):
    from aiogram import Dispatcher
    dp = Dispatcher()
    dp.include_router(build_router(pool, admin_ids))
    return dp