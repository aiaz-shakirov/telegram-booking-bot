# Booking Bot

Telegram-бот для записи к мастерам с инлайн-кнопками и админ-панелью. REST API поверх той же базы данных.

**Стек:** aiogram 3.x, FastAPI, PostgreSQL (asyncpg).

## Возможности

**Пользователь:**
- Запись через инлайн-кнопки: мастер → дата → время → имя
- `/mybookings` — просмотр и отмена своих записей

**Админ:**
- `/admin` — панель управления
- Просмотр и отмена любых записей
- Добавление и удаление мастеров

## Установка

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Скопируй `.env.example` в `.env` и заполни своими данными:

```bash
cp .env.example .env
```

- `TELEGRAM_API_TOKEN` — получить у [@BotFather](https://t.me/BotFather)
- `DATABASE_*` — данные подключения к твоей PostgreSQL
- `ADMIN_IDS` — твой Telegram ID через запятую
- `API_KEY` — секретный ключ для защищённых эндпоинтов API.

## Аутентификация API

Эндпоинты `POST /bookings` и `DELETE /bookings/{id}` требуют заголовок `X-API-Key`:

```bash
curl -X POST "http://localhost:8000/bookings" \
  -H "X-API-Key: твой_ключ_из_env" \
  -H "Content-Type: application/json" \
  -d '{"master_id": 1, "telegram_id": 123, "client_name": "Тест", "booking_time": "2026-09-20T15:00:00"}'
```

Эндпоинты на чтение (`GET`) остаются открытыми.


## Запуск

```bash
python main.py
```

Бот и API поднимутся вместе. API-документация: `http://localhost:8000/docs`

## Структура

```
├── database.py   # запросы к PostgreSQL (asyncpg)
├── bot.py        # логика бота (aiogram, инлайн-кнопки, админка)
├── api.py        # REST API (FastAPI)
├── main.py       # запускает бота и API одновременно
└── requirements.txt
```