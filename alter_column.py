from app.database import engine
from sqlalchemy import text

with engine.begin() as conn:
    conn.execute(text("ALTER TABLE orders RENAME COLUMN note TO notes"))
    print("Столбец успешно переименован")