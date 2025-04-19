from app.database import engine
from sqlalchemy import text

with engine.begin() as conn:
    conn.execute(text("ALTER TABLE orders ADD COLUMN notes TEXT"))
    print("Столбец успешно добавлен")