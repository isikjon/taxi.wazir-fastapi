"""
Скрипт для исправления формата рейтинга в таблице drivers.
Заменяет запятую на точку во всех значениях поля rating.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем URL базы данных
database_url = os.getenv("DATABASE_URL")

if not database_url:
    print("Ошибка: Не найдена переменная окружения DATABASE_URL")
    exit(1)

# Создаем подключение к базе данных
engine = create_engine(database_url)

def fix_rating_format():
    """
    Функция для исправления формата рейтинга в таблице drivers.
    Заменяет запятую на точку во всех значениях поля rating.
    """
    try:
        # Сначала получаем все записи с запятой в рейтинге
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, rating FROM drivers WHERE rating LIKE '%,%'"))
            rows = result.fetchall()
            
            if not rows:
                print("Записи с неправильным форматом рейтинга не найдены.")
                return
            
            print(f"Найдено {len(rows)} записей с неправильным форматом рейтинга.")
            
            # Обновляем каждую запись
            for row in rows:
                driver_id = row[0]
                rating = row[1].replace(',', '.')
                
                conn.execute(
                    text("UPDATE drivers SET rating = :rating WHERE id = :id"),
                    {"rating": rating, "id": driver_id}
                )
                print(f"Обновлен рейтинг для водителя с ID {driver_id}: {row[1]} -> {rating}")
            
            conn.commit()
            print("Все записи успешно обновлены.")
            
    except Exception as e:
        print(f"Ошибка при обновлении записей: {str(e)}")

if __name__ == "__main__":
    print("Начинаем исправление формата рейтинга...")
    fix_rating_format()
    print("Процесс завершен.") 