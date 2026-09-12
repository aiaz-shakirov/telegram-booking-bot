from fastapi import FastAPI, HTTPException
from typing import Optional
from pydantic import BaseModel
import asyncpg
from datetime import datetime
import database as db

class MasterOut(BaseModel):
    id: int
    name: str

class BookingOut(BaseModel):
    id: int
    master_id: int
    telegram_id: int
    client_name: str
    booking_time: datetime
    status: str

class BookingCreate(BaseModel):
    master_id: int
    telegram_id: int
    client_name: str
    booking_name: datetime

def create_api_app(pool: asyncpg.Pool) -> FastAPI:
    app = FastAPI(title="Booking Bot API")
    app.state.pool = pool

    @app.get('/health')
    async def health():
        return {"status": "ok"}

    @app.get("/masters", response_model=list[MasterOut])
    async def get_masters():
        masters = await db.list_masters(app.state.pool)
        return [MasterOut(**dict(m)) for m in masters]

    @app.get("/masters/{master_id}/bookings", response_model=list[BookingOut])
    async def get_master_bookings(master_id: int, from_time: Optional[datetime] = None):
        bookings = await db.list_bookings_by_master(app.state.pool, master_id, from_time)
        return [BookingOut(**dict(b)) for b in bookings]

    @app.post("/bookings", response_model=BookingOut)
    async def create_booking(payload: BookingCreate):
        booking = await db.create_booking(
            app.state.pool,
            master_id=payload.master_id,
            telegram_id=payload.telegram_id,
            client_name=payload.client_name,
            booking_time=payload.booking_name
        )
        if booking is None:
            raise HTTPException(status_code=409, detail="Это время уже занято")
        return BookingOut(**dict(booking))

    @app.get("/users/{telegram_id}/bookings", response_model=list[BookingOut])
    async def get_user_bookings(telegram_id: int):
        bookings = await db.list_bookings_by_user(app.state.pool, telegram_id)
        result = []
        for b in bookings:
            result.append(BookingOut(
                id=b["id"],
                master_id=b["master_id"],
                telegram_id=b["telegram_id"],
                client_name=b["client_name"],
                booking_time=b["booking_time"],
                status=b["status"]
            ))
        return result
    @app.delete("/bookings/{booking_id}")
    async def cancel_booking(booking_id: int, telegram_id: int):
        cancelled = await db.cancel_booking(app.state.pool, booking_id, telegram_id)
        if cancelled is None:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        return {"status": "cancelled", "booking_id": booking_id}

    return app
