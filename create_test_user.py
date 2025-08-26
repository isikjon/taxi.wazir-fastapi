#!/usr/bin/env python3
"""
Скрипт для создания тестового пользователя в базе данных
"""

import sys
import os
sys.path.append('.')

from app.database import SessionLocal
from app import models, schemas, crud

def create_test_user():
    """Создает тестового пользователя +9961111111111"""
    db = SessionLocal()
    
    try:
        phone = "9961111111111"
        print(f"🧪 Создаем тестового пользователя с номером: {phone}")
        
        # Проверяем, существует ли пользователь
        existing_user = crud.get_driver_user_by_phone(db, phone)
        if existing_user:
            print(f"✅ Пользователь уже существует:")
            print(f"   ID: {existing_user.id}")
            print(f"   Телефон: {existing_user.phone}")
            print(f"   Имя: {existing_user.first_name}")
            print(f"   Фамилия: {existing_user.last_name}")
            print(f"   Верифицирован: {existing_user.is_verified}")
            print(f"   Driver ID: {existing_user.driver_id}")
            return existing_user
        
        # Создаем нового пользователя
        user_data = schemas.DriverUserCreate(
            phone=phone,
            first_name="Тестовый",
            last_name="Водитель"
        )
        
        user = crud.create_driver_user(db, user_data)
        print(f"✅ Пользователь создан:")
        print(f"   ID: {user.id}")
        print(f"   Телефон: {user.phone}")
        print(f"   Имя: {user.first_name}")
        print(f"   Фамилия: {user.last_name}")
        
        return user
        
    except Exception as e:
        print(f"❌ Ошибка при создании пользователя: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def create_test_driver():
    """Создает тестового водителя"""
    db = SessionLocal()
    
    try:
        phone = "9961111111111"
        print(f"\n👨‍💼 Создаем тестового водителя с номером: {phone}")
        
        # Проверяем, существует ли водитель
        existing_driver = db.query(models.Driver).filter(models.Driver.phone == phone).first()
        if existing_driver:
            print(f"✅ Водитель уже существует:")
            print(f"   ID: {existing_driver.id}")
            print(f"   Имя: {existing_driver.full_name}")
            print(f"   Телефон: {existing_driver.phone}")
            print(f"   Статус: {existing_driver.status}")
            return existing_driver
        
        # Создаем нового водителя
        driver_data = {
            "full_name": "Тестовый Водитель Иванов",
            "birth_date": "1990-01-01",
            "callsign": "ТЕСТ001",
            "unique_id": "TEST000000000000001",
            "city": "Бишкек",
            "driver_license_number": "TEST123456789",
            "driver_license_issue_date": "2020-01-01",
            "balance": 1000.0,
            "tariff": "Стандартный",
            "taxi_park": "Тестовый Парк",
            "phone": phone,
            "status": "accepted",
            "activity": 10,
            "rating": "5.000"
        }
        
        driver = models.Driver(**driver_data)
        db.add(driver)
        db.commit()
        db.refresh(driver)
        
        print(f"✅ Водитель создан:")
        print(f"   ID: {driver.id}")
        print(f"   Имя: {driver.full_name}")
        print(f"   Телефон: {driver.phone}")
        print(f"   Статус: {driver.status}")
        
        # Связываем пользователя с водителем
        user = crud.get_driver_user_by_phone(db, phone)
        if user:
            user.driver_id = driver.id
            db.commit()
            print(f"✅ Пользователь связан с водителем")
        
        return driver
        
    except Exception as e:
        print(f"❌ Ошибка при создании водителя: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Создание тестовых данных для авторизации...")
    
    try:
        # Создаем пользователя
        user = create_test_user()
        
        # Создаем водителя
        driver = create_test_driver()
        
        print("\n🎉 Тестовые данные созданы успешно!")
        print(f"📱 Теперь можно войти с номером: +9961111111111")
        print(f"🔑 Код подтверждения: 1111")
        
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        sys.exit(1)
