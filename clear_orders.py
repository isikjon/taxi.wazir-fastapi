#!/usr/bin/env python3
"""
Скрипт для очистки таблицы заказов
Удаляет все записи из таблицы orders, но сохраняет структуру таблицы
"""

import sys
import os
sys.path.append('.')

from app.database import SessionLocal, engine
from app import models
from sqlalchemy import text

def clear_orders_table():
    """Очищает таблицу заказов"""
    db = SessionLocal()
    
    try:
        print("🗑️  Начинаем очистку таблицы заказов...")
        
        # Подсчитываем количество заказов до удаления
        orders_count = db.query(models.Order).count()
        print(f"📊 Найдено заказов для удаления: {orders_count}")
        
        if orders_count == 0:
            print("✅ Таблица заказов уже пуста")
            return
        
        # Удаляем все заказы
        deleted_count = db.query(models.Order).delete()
        db.commit()
        
        print(f"✅ Успешно удалено {deleted_count} заказов")
        
        # Сбрасываем автоинкремент (для SQLite)
        try:
            db.execute(text("DELETE FROM sqlite_sequence WHERE name='orders'"))
            db.commit()
            print("🔄 Автоинкремент ID сброшен")
        except Exception as e:
            print(f"⚠️  Не удалось сбросить автоинкремент: {e}")
        
        # Проверяем что таблица пуста
        remaining_count = db.query(models.Order).count()
        print(f"📊 Заказов осталось: {remaining_count}")
        
        if remaining_count == 0:
            print("🎉 Таблица заказов успешно очищена!")
        else:
            print(f"⚠️  Остались не удаленные заказы: {remaining_count}")
            
    except Exception as e:
        print(f"❌ Ошибка при очистке таблицы: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def clear_related_tables():
    """Опционально очищает связанные таблицы"""
    db = SessionLocal()
    
    try:
        print("\n🗑️  Очистка связанных таблиц...")
        
        # Очищаем транзакции баланса
        balance_count = db.query(models.BalanceTransaction).count()
        if balance_count > 0:
            db.query(models.BalanceTransaction).delete()
            print(f"💰 Удалено транзакций баланса: {balance_count}")
        
        # Очищаем сообщения
        messages_count = db.query(models.Message).count()
        if messages_count > 0:
            db.query(models.Message).delete()
            print(f"💬 Удалено сообщений: {messages_count}")
        
        db.commit()
        print("✅ Связанные таблицы очищены")
        
    except Exception as e:
        print(f"❌ Ошибка при очистке связанных таблиц: {e}")
        db.rollback()
    finally:
        db.close()

def reset_driver_states():
    """Сбрасываем состояние водителей (убираем активные заказы)"""
    db = SessionLocal()
    
    try:
        print("\n👨‍💼 Сбрасываем состояние водителей...")
        
        # Ставим всех водителей в офлайн и сбрасываем текущие координаты
        drivers = db.query(models.Driver).all()
        updated_count = 0
        
        for driver in drivers:
            driver.is_online = False
            driver.current_lat = None
            driver.current_lng = None
            driver.last_location_update = None
            updated_count += 1
        
        db.commit()
        print(f"✅ Обновлено водителей: {updated_count}")
        
    except Exception as e:
        print(f"❌ Ошибка при сбросе состояния водителей: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🚨 ВНИМАНИЕ: Этот скрипт удалит ВСЕ заказы из базы данных!")
    print("📍 База данных:", engine.url)
    
    response = input("\n❓ Вы уверены что хотите продолжить? (yes/no): ").lower().strip()
    
    if response in ['yes', 'y', 'да', 'д']:
        try:
            # Основная очистка
            clear_orders_table()
            
            # Спрашиваем про связанные таблицы
            response2 = input("\n❓ Очистить связанные таблицы (сообщения, транзакции)? (yes/no): ").lower().strip()
            if response2 in ['yes', 'y', 'да', 'д']:
                clear_related_tables()
            
            # Спрашиваем про сброс состояния водителей
            response3 = input("\n❓ Сбросить состояние водителей (офлайн, координаты)? (yes/no): ").lower().strip()
            if response3 in ['yes', 'y', 'да', 'д']:
                reset_driver_states()
            
            print("\n🎉 Операция завершена успешно!")
            print("💡 Рекомендуется перезапустить FastAPI сервер")
            
        except Exception as e:
            print(f"\n💥 Критическая ошибка: {e}")
            sys.exit(1)
    else:
        print("❌ Операция отменена пользователем")
        sys.exit(0)
