#!/usr/bin/env python3
"""Скрипт для сброса статуса верификации водителя"""

import sys
sys.path.append('.')

from app.database import engine
from app import models
from sqlalchemy.orm import Session

def main():
    print("🔧 Сброс статуса верификации водителя 1...")
    
    with Session(engine) as db:
        # Находим все верификации фотоконтроля для водителя 1
        verifications = db.query(models.DriverVerification).filter(
            models.DriverVerification.driver_id == 1,
            models.DriverVerification.verification_type == "photo_control"
        ).all()
        
        print(f"Найдено верификаций: {len(verifications)}")
        
        for v in verifications:
            print(f"  ID: {v.id}, статус: {v.status}, дата: {v.created_at}")
        
        if verifications:
            # Удаляем все верификации
            for v in verifications:
                db.delete(v)
            
            db.commit()
            print("✅ Все верификации удалены")
        else:
            print("ℹ️  Верификации не найдены")
        
        # Также очищаем документы
        docs = db.query(models.DriverDocuments).filter(
            models.DriverDocuments.driver_id == 1
        ).first()
        
        if docs:
            print(f"Найдены документы: {docs.id}")
            db.delete(docs)
            db.commit()
            print("✅ Документы удалены")
        else:
            print("ℹ️  Документы не найдены")
            
        print("🎉 Теперь можно загружать фотографии заново")

if __name__ == "__main__":
    main()
