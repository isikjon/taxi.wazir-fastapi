#!/usr/bin/env python3
"""Скрипт для отладки состояния БД"""

import sys
sys.path.append('.')

from app.database import engine, get_db
from app import models
from sqlalchemy.orm import Session

def main():
    print("🔍 Проверка состояния базы данных...")
    
    # Проверяем, существует ли таблица driver_documents
    try:
        with engine.connect() as conn:
            result = conn.execute("SELECT 1 FROM driver_documents LIMIT 1")
            print("✅ Таблица driver_documents существует")
    except Exception as e:
        print(f"❌ Таблица driver_documents НЕ существует: {e}")
        
        # Попробуем создать таблицы
        try:
            print("🔧 Создаем таблицы...")
            models.Base.metadata.create_all(bind=engine)
            print("✅ Таблицы созданы успешно")
        except Exception as create_e:
            print(f"❌ Ошибка создания таблиц: {create_e}")
            return
    
    # Проверяем водителя 1
    with Session(engine) as db:
        driver = db.query(models.Driver).filter(models.Driver.id == 1).first()
        if driver:
            print(f"✅ Водитель найден: {driver.full_name}")
            
            # Проверяем документы
            docs = db.query(models.DriverDocuments).filter(
                models.DriverDocuments.driver_id == 1
            ).first()
            
            if docs:
                print(f"✅ Документы найдены:")
                print(f"  passport_front: {docs.passport_front}")
                print(f"  passport_back: {docs.passport_back}")
                print(f"  license_front: {docs.license_front}")
                print(f"  license_back: {docs.license_back}")
                print(f"  driver_with_license: {docs.driver_with_license}")
            else:
                print("❌ Документы НЕ найдены")
                
                # Создаем пустую запись документов
                new_docs = models.DriverDocuments(driver_id=1)
                db.add(new_docs)
                db.commit()
                print("✅ Создана пустая запись документов")
            
            # Проверяем верификацию
            verification = db.query(models.DriverVerification).filter(
                models.DriverVerification.driver_id == 1,
                models.DriverVerification.verification_type == "photo_control"
            ).order_by(models.DriverVerification.created_at.desc()).first()
            
            if verification:
                print(f"✅ Верификация найдена: {verification.status}")
            else:
                print("❌ Верификация НЕ найдена")
                
        else:
            print("❌ Водитель с ID=1 не найден")

if __name__ == "__main__":
    main()
