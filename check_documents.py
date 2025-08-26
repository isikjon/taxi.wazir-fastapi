#!/usr/bin/env python3
"""Скрипт для проверки содержимого таблицы driver_documents"""

import sys
sys.path.append('.')

from app.database import engine
from app import models
from sqlalchemy.orm import Session

def main():
    print("🔍 Проверка таблицы driver_documents...")
    
    with Session(engine) as db:
        # Получаем все записи
        all_docs = db.query(models.DriverDocuments).all()
        
        print(f"Всего записей в driver_documents: {len(all_docs)}")
        
        for doc in all_docs:
            print(f"\n📋 ID: {doc.id}, driver_id: {doc.driver_id}")
            print(f"  passport_front: {doc.passport_front}")
            print(f"  passport_back: {doc.passport_back}")
            print(f"  license_front: {doc.license_front}")
            print(f"  license_back: {doc.license_back}")
            print(f"  driver_with_license: {doc.driver_with_license}")
            print(f"  is_verified: {doc.is_verified}")

if __name__ == "__main__":
    main()
