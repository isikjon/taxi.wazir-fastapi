#!/usr/bin/env python3

import sys
sys.path.append('.')

from app.database import engine
from app import models
from sqlalchemy.orm import Session

def main():
    print("🧹 Очистка данных верификации водителя 1...")
    
    with Session(engine) as db:
        # Удаляем все верификации
        verifications = db.query(models.DriverVerification).filter(
            models.DriverVerification.driver_id == 1
        ).all()
        
        for v in verifications:
            print(f"Удаляем верификацию: {v.verification_type} - {v.status}")
            db.delete(v)
        
        # Очищаем пути документов
        docs = db.query(models.DriverDocuments).filter(
            models.DriverDocuments.driver_id == 1
        ).first()
        
        if docs:
            print("Очищаем пути к документам...")
            docs.passport_front = None
            docs.passport_back = None
            docs.license_front = None
            docs.license_back = None
            docs.driver_with_license = None
        
        db.commit()
        print("✅ Данные очищены, можно загружать фотографии заново")

if __name__ == "__main__":
    main()
