import asyncpg

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS masters (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bookings (
    id SERIAL PRIMARY KEY,
    master_id INT NOT NULL REFERENCES masters(id),
    telegram_id BIGINT NOT NULL,
    client_name TEXT NOT NULL,
    booking_time TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (master_id, booking_time)
);
"""


async def create_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=10)


async def init_db(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)


async def list_masters(pool: asyncpg.Pool) -> list[asyncpg.Record]:
    query = "SELECT * FROM masters ORDER BY name;"
    async with pool.acquire() as conn:
        return await conn.fetch(query)


async def add_master(pool: asyncpg.Pool, name: str) -> asyncpg.Record:
    query = "INSERT INTO masters (name) VALUES ($1) RETURNING *;"
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, name)


async def delete_master(pool: asyncpg.Pool, master_id: int) -> bool:
    query = "DELETE FROM masters WHERE id = $1;"
    async with pool.acquire() as conn:
        try:
            result = await conn.execute(query, master_id)
        except asyncpg.ForeignKeyViolationError:
            return False
    return result.endswith(" 1")


async def create_booking(pool, master_id, telegram_id, client_name, booking_time):
    query = """
    INSERT INTO bookings (master_id, telegram_id, client_name, booking_time)
    VALUES ($1, $2, $3, $4)
    RETURNING *;
    """
    async with pool.acquire() as conn:
        try:
            return await conn.fetchrow(query, master_id, telegram_id, client_name, booking_time)
        except asyncpg.UniqueViolationError:
            return None


async def list_bookings_by_master(pool, master_id, from_time=None):
    async with pool.acquire() as conn:
        if from_time:
            query = """
            SELECT * FROM bookings
            WHERE master_id = $1 AND status = 'confirmed' AND booking_time >= $2
            ORDER BY booking_time;
            """
            return await conn.fetch(query, master_id, from_time)
        query = """
        SELECT * FROM bookings
        WHERE master_id = $1 AND status = 'confirmed'
        ORDER BY booking_time;
        """
        return await conn.fetch(query, master_id)


async def list_bookings_by_user(pool, telegram_id):
    query = """
    SELECT b.*, m.name AS master_name FROM bookings b
    JOIN masters m ON m.id = b.master_id
    WHERE b.telegram_id = $1 AND b.status = 'confirmed'
    ORDER BY b.booking_time;
    """
    async with pool.acquire() as conn:
        return await conn.fetch(query, telegram_id)


async def list_all_upcoming_bookings(pool, limit: int = 20):
    query = """
    SELECT b.*, m.name AS master_name FROM bookings b
    JOIN masters m ON m.id = b.master_id
    WHERE b.status = 'confirmed' AND b.booking_time >= now()
    ORDER BY b.booking_time
    LIMIT $1;
    """
    async with pool.acquire() as conn:
        return await conn.fetch(query, limit)


async def cancel_booking(pool, booking_id, telegram_id):
    query = """
    UPDATE bookings
    SET status = 'cancelled'
    WHERE id = $1 AND telegram_id = $2
    RETURNING *;
    """
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, booking_id, telegram_id)


async def admin_cancel_booking(pool, booking_id):
    query = """
    UPDATE bookings
    SET status = 'cancelled'
    WHERE id = $1
    RETURNING *;
    """
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, booking_id)