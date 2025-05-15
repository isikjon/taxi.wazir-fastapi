from sqlalchemy import create_engine, text
from .database import SQLALCHEMY_DATABASE_URL

def run_migrations():
    """Применяет миграции для добавления новых столбцов в таблицу drivers"""
    
    print("Запуск миграций базы данных...")
    
    # Подключение к базе данных
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    conn = engine.connect()
    
    try:
        # Проверяем наличие колонки is_mobile_registered
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'drivers' AND column_name = 'is_mobile_registered'
        """))
        
        if not result.scalar():
            print("Добавление колонки is_mobile_registered...")
            conn.execute(text("""
                ALTER TABLE drivers 
                ADD COLUMN is_mobile_registered BOOLEAN DEFAULT FALSE
            """))
            conn.commit()
            print("Колонка is_mobile_registered успешно добавлена.")
        else:
            print("Колонка is_mobile_registered уже существует.")
        
        # Проверяем наличие колонки registration_date
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'drivers' AND column_name = 'registration_date'
        """))
        
        if not result.scalar():
            print("Добавление колонки registration_date...")
            conn.execute(text("""
                ALTER TABLE drivers 
                ADD COLUMN registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """))
            conn.commit()
            print("Колонка registration_date успешно добавлена.")
        else:
            print("Колонка registration_date уже существует.")
            
        print("Миграции успешно выполнены.")
        
    except Exception as e:
        conn.rollback()
        print(f"Ошибка при выполнении миграций: {str(e)}")
        raise
    finally:
        conn.close()
        
if __name__ == "__main__":
    run_migrations() 