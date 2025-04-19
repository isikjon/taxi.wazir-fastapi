from sqlalchemy import create_engine, text
from app.database import SQLALCHEMY_DATABASE_URL
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

engine = create_engine(SQLALCHEMY_DATABASE_URL)

try:
    with engine.begin() as conn:
        logger.info("Проверяем наличие столбца phone в таблице drivers")
        result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'drivers' AND column_name = 'phone'"))
        if result.fetchone() is None:
            logger.info("Столбец phone отсутствует. Добавляем столбец phone в таблицу drivers")
            conn.execute(text("ALTER TABLE drivers ADD COLUMN phone VARCHAR(50)"))
            logger.info("Столбец phone успешно добавлен в таблицу drivers")
        else:
            logger.info("Столбец phone уже существует в таблице drivers")
        
        logger.info("Проверяем наличие столбца color в таблице cars")
        result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'cars' AND column_name = 'color'"))
        if result.fetchone() is None:
            logger.info("Столбец color отсутствует. Добавляем столбец color в таблицу cars")
            conn.execute(text("ALTER TABLE cars ADD COLUMN color VARCHAR(50)"))
            logger.info("Столбец color успешно добавлен в таблицу cars")
        else:
            logger.info("Столбец color уже существует в таблице cars")

    logger.info("Обновление схемы базы данных завершено успешно!")
except Exception as e:
    logger.error(f"Ошибка при обновлении схемы: {e}")
