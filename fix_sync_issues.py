#!/usr/bin/env python
# -*- coding: utf-8 -*-
import psycopg2
import psycopg2.extras
import sys

# Настройки подключения к базе данных
DB_CONFIG = {
    'dbname': 'wazir',
    'user': 'postgres',
    'password': '123',
    'host': 'localhost',
    'port': '5432'
}

def connect_to_db():
    """Подключение к базе данных"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        print("✅ Успешное подключение к базе данных")
        return conn, cursor
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        sys.exit(1)

def close_connection(conn, cursor):
    """Закрытие соединения с базой данных"""
    if cursor:
        cursor.close()
    if conn:
        conn.close()
    print("👋 Соединение с базой данных закрыто")

def fix_tariff_sync(cursor):
    """Исправление синхронизации тарифов"""
    print("\n🔧 Исправление синхронизации тарифов...")
    
    # Проверка текущих значений
    cursor.execute("""
        SELECT d.id, d.full_name, d.tariff_id, d.tariff, t.name as tariff_name
        FROM drivers d
        LEFT JOIN tariffs t ON d.tariff_id = t.id
        ORDER BY d.id;
    """)
    
    drivers = cursor.fetchall()
    if not drivers:
        print("⚠️ Нет данных о водителях")
        return
    
    # Вывод текущих значений
    print("\nТекущие значения тарифов:")
    for driver in drivers:
        print(f"ID: {driver['id']}, Имя: {driver['full_name']}, ID тарифа: {driver['tariff_id']}, Тариф: {driver['tariff']}, Название тарифа: {driver['tariff_name']}")
    
    # Исправление значений с ID тарифа
    cursor.execute("""
        UPDATE drivers d
        SET tariff = t.name
        FROM tariffs t
        WHERE d.tariff_id = t.id AND d.tariff != t.name
        RETURNING d.id, d.full_name, d.tariff;
    """)
    
    updated_drivers = cursor.fetchall()
    if updated_drivers:
        print("\n✅ Обновлены тарифы для следующих водителей (на основе ID тарифа):")
        for driver in updated_drivers:
            print(f"ID: {driver['id']}, Имя: {driver['full_name']}, Тариф: {driver['tariff']}")
    
    # Исправление ID тарифа на основе названия
    cursor.execute("""
        UPDATE drivers d
        SET tariff_id = t.id
        FROM tariffs t
        WHERE d.tariff = t.name AND (d.tariff_id IS NULL OR d.tariff_id != t.id)
        RETURNING d.id, d.full_name, d.tariff_id, d.tariff;
    """)
    
    updated_drivers = cursor.fetchall()
    if updated_drivers:
        print("\n✅ Обновлены ID тарифов для следующих водителей (на основе названия тарифа):")
        for driver in updated_drivers:
            print(f"ID: {driver['id']}, Имя: {driver['full_name']}, ID тарифа: {driver['tariff_id']}, Тариф: {driver['tariff']}")
    
    # Исправление бизнес-тарифа
    cursor.execute("""
        UPDATE drivers 
        SET tariff = 'Business', 
            tariff_id = (SELECT id FROM tariffs WHERE name = 'Business' OR name ILIKE '%business%' LIMIT 1)
        WHERE tariff ILIKE '%business%' OR tariff ILIKE '%бизнес%'
        RETURNING id, full_name, tariff, tariff_id;
    """)
    
    updated_business = cursor.fetchall()
    if updated_business:
        print("\n✅ Обновлены бизнес-тарифы для следующих водителей:")
        for driver in updated_business:
            print(f"ID: {driver['id']}, Имя: {driver['full_name']}, Тариф: {driver['tariff']}, ID тарифа: {driver['tariff_id']}")
    
    # Исправление эконом-тарифа
    cursor.execute("""
        UPDATE drivers 
        SET tariff = 'Эконом', 
            tariff_id = (SELECT id FROM tariffs WHERE name = 'Эконом' OR name ILIKE '%эконом%' LIMIT 1)
        WHERE tariff ILIKE '%эконом%' OR tariff ILIKE '%econom%'
        RETURNING id, full_name, tariff, tariff_id;
    """)
    
    updated_economy = cursor.fetchall()
    if updated_economy:
        print("\n✅ Обновлены эконом-тарифы для следующих водителей:")
        for driver in updated_economy:
            print(f"ID: {driver['id']}, Имя: {driver['full_name']}, Тариф: {driver['tariff']}, ID тарифа: {driver['tariff_id']}")
    
    # Исправление комфорт-тарифа
    cursor.execute("""
        UPDATE drivers 
        SET tariff = 'Комфорт', 
            tariff_id = (SELECT id FROM tariffs WHERE name = 'Комфорт' OR name ILIKE '%комфорт%' LIMIT 1)
        WHERE tariff ILIKE '%комфорт%' OR tariff ILIKE '%comfort%'
        RETURNING id, full_name, tariff, tariff_id;
    """)
    
    updated_comfort = cursor.fetchall()
    if updated_comfort:
        print("\n✅ Обновлены комфорт-тарифы для следующих водителей:")
        for driver in updated_comfort:
            print(f"ID: {driver['id']}, Имя: {driver['full_name']}, Тариф: {driver['tariff']}, ID тарифа: {driver['tariff_id']}")
    
    # Проверка результатов
    cursor.execute("""
        SELECT d.id, d.full_name, d.tariff_id, d.tariff, t.name as tariff_name
        FROM drivers d
        LEFT JOIN tariffs t ON d.tariff_id = t.id
        ORDER BY d.id;
    """)
    
    final_drivers = cursor.fetchall()
    
    print("\nРезультаты после исправления:")
    for driver in final_drivers:
        is_synced = driver['tariff'] == driver['tariff_name'] if driver['tariff_name'] else False
        status = "✅ Синхронизировано" if is_synced else "❌ Не синхронизировано"
        print(f"ID: {driver['id']}, Имя: {driver['full_name']}, ID тарифа: {driver['tariff_id']}, Тариф: {driver['tariff']}, Название тарифа: {driver['tariff_name']} - {status}")
    
    # Общие результаты
    synced_count = sum(1 for d in final_drivers if (d['tariff'] == d['tariff_name'] if d['tariff_name'] else False))
    total_count = len(final_drivers)
    print(f"\nИтого: {synced_count} из {total_count} водителей имеют синхронизированные тарифы")

def fix_car_data_sync(cursor):
    """Исправление синхронизации данных автомобилей между таблицами cars и driver_cars"""
    print("\n🔧 Исправление синхронизации данных автомобилей...")
    
    # Проверяем структуру таблиц cars и driver_cars
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'cars' 
        ORDER BY ordinal_position;
    """)
    cars_columns = cursor.fetchall()
    
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'driver_cars' 
        ORDER BY ordinal_position;
    """)
    driver_cars_columns = cursor.fetchall()
    
    print("\nСтруктура таблицы cars:")
    for col in cars_columns:
        print(f"  {col['column_name']} ({col['data_type']})")
    
    print("\nСтруктура таблицы driver_cars:")
    for col in driver_cars_columns:
        print(f"  {col['column_name']} ({col['data_type']})")
    
    # Получаем данные об автомобилях
    cursor.execute("""
        SELECT c.id, c.driver_id, c.brand, c.model, c.license_plate, c.year, c.color
        FROM cars c
        ORDER BY c.driver_id;
    """)
    cars = cursor.fetchall()
    
    cursor.execute("""
        SELECT dc.id, dc.driver_id, dc.make AS brand, dc.model, dc.license_plate, dc.year, dc.color
        FROM driver_cars dc
        ORDER BY dc.driver_id;
    """)
    driver_cars = cursor.fetchall()
    
    # Создаем словари для быстрого поиска
    cars_by_driver = {car['driver_id']: car for car in cars if car['driver_id']}
    driver_cars_by_driver = {dc['driver_id']: dc for dc in driver_cars if dc['driver_id']}
    
    # Проверяем несоответствия и создаем/обновляем записи
    missing_in_driver_cars = []
    mismatched_data = []
    
    for driver_id, car in cars_by_driver.items():
        if driver_id not in driver_cars_by_driver:
            missing_in_driver_cars.append(car)
        else:
            driver_car = driver_cars_by_driver[driver_id]
            # Проверяем несоответствия в данных
            if (car['brand'] != driver_car['brand'] or 
                car['model'] != driver_car['model'] or 
                car['license_plate'] != driver_car['license_plate'] or 
                car['year'] != driver_car['year'] or 
                car['color'] != driver_car['color']):
                mismatched_data.append((car, driver_car))
    
    # Исправляем несоответствия
    for car in missing_in_driver_cars:
        try:
            cursor.execute("""
                INSERT INTO driver_cars (driver_id, make, model, license_plate, year, color)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                car['driver_id'], car['brand'], car['model'], 
                car['license_plate'], car['year'], car['color']
            ))
            new_id = cursor.fetchone()[0]
            print(f"✅ Создана запись в driver_cars для водителя ID: {car['driver_id']} (новый ID: {new_id})")
        except Exception as e:
            print(f"❌ Ошибка при создании записи для водителя {car['driver_id']}: {e}")
    
    for car, driver_car in mismatched_data:
        try:
            cursor.execute("""
                UPDATE driver_cars
                SET make = %s, model = %s, license_plate = %s, year = %s, color = %s
                WHERE id = %s;
            """, (
                car['brand'], car['model'], car['license_plate'],
                car['year'], car['color'], driver_car['id']
            ))
            print(f"✅ Обновлены данные в driver_cars для водителя ID: {car['driver_id']} (ID записи: {driver_car['id']})")
        except Exception as e:
            print(f"❌ Ошибка при обновлении данных для водителя {car['driver_id']}: {e}")
    
    # Проверка результатов
    cursor.execute("""
        SELECT c.id as car_id, c.driver_id, c.brand as car_brand, c.model as car_model, 
               c.license_plate as car_plate, c.year as car_year, c.color as car_color,
               dc.id as dc_id, dc.make as dc_brand, dc.model as dc_model, 
               dc.license_plate as dc_plate, dc.year as dc_year, dc.color as dc_color
        FROM cars c
        LEFT JOIN driver_cars dc ON c.driver_id = dc.driver_id
        WHERE c.driver_id IS NOT NULL
        ORDER BY c.driver_id;
    """)
    
    result = cursor.fetchall()
    
    print("\nРезультаты после исправления:")
    for row in result:
        is_synced = (row['car_brand'] == row['dc_brand'] and 
                     row['car_model'] == row['dc_model'] and 
                     row['car_plate'] == row['dc_plate'] and 
                     row['car_year'] == row['dc_year'] and 
                     row['car_color'] == row['dc_color'])
        
        status = "✅ Синхронизировано" if is_synced else "❌ Не синхронизировано"
        print(f"Водитель ID: {row['driver_id']}, Автомобиль: {row['car_brand']} {row['car_model']} ({row['car_plate']}) - {status}")
    
    # Итоги
    synced_count = sum(1 for r in result if (r['car_brand'] == r['dc_brand'] and 
                                             r['car_model'] == r['dc_model'] and 
                                             r['car_plate'] == r['dc_plate'] and 
                                             r['car_year'] == r['dc_year'] and 
                                             r['car_color'] == r['dc_color']))
    total_count = len(result)
    print(f"\nИтого: {synced_count} из {total_count} автомобилей имеют синхронизированные данные")

def fix_driver_data_sync(cursor):
    """Исправление синхронизации данных водителей между таблицами drivers и driver_users"""
    print("\n🔧 Исправление синхронизации данных водителей...")
    
    # Проверяем структуру таблицы drivers
    cursor.execute("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'drivers' 
        ORDER BY ordinal_position;
    """)
    
    drivers_columns = cursor.fetchall()
    print("\nСтруктура таблицы drivers:")
    for col in drivers_columns:
        print(f"  {col['column_name']} ({col['data_type']})")
    
    # Получаем данные о водителях
    cursor.execute("""
        SELECT d.id, d.full_name, d.phone, 
               du.id as du_id, du.phone as du_phone, du.first_name as du_first_name, 
               du.last_name as du_last_name, du.driver_id
        FROM drivers d
        LEFT JOIN driver_users du ON d.id = du.driver_id
        ORDER BY d.id;
    """)
    
    drivers = cursor.fetchall()
    
    if not drivers:
        print("⚠️ Нет данных о водителях")
        return
    
    missing_in_driver_users = []
    mismatched_data = []
    
    for driver in drivers:
        if driver['du_id'] is None:
            missing_in_driver_users.append(driver)
        elif driver['phone'] != driver['du_phone']:
            mismatched_data.append(driver)
    
    # Исправляем отсутствующие записи
    for driver in missing_in_driver_users:
        try:
            # Генерируем данные для новой записи
            names = driver['full_name'].split() if driver['full_name'] else ["", ""]
            first_name = names[0] if len(names) > 0 else ""
            last_name = names[1] if len(names) > 1 else ""
            default_password = "pbkdf2:sha256:150000$" + "defaultpassword"
            
            cursor.execute("""
                INSERT INTO driver_users (driver_id, phone, password, first_name, last_name)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (
                driver['id'], driver['phone'], default_password, first_name, last_name
            ))
            
            new_id = cursor.fetchone()[0]
            print(f"✅ Создана запись в driver_users для водителя ID: {driver['id']} (новый ID: {new_id})")
        except Exception as e:
            print(f"❌ Ошибка при создании записи для водителя {driver['id']}: {e}")
    
    # Исправляем несоответствия в телефонах
    for driver in mismatched_data:
        try:
            cursor.execute("""
                UPDATE driver_users
                SET phone = %s
                WHERE id = %s;
            """, (driver['phone'], driver['du_id']))
            print(f"✅ Обновлен телефон в driver_users для водителя ID: {driver['id']} (запись ID: {driver['du_id']})")
        except Exception as e:
            print(f"❌ Ошибка при обновлении данных для водителя {driver['id']}: {e}")
    
    # Проверка результатов
    cursor.execute("""
        SELECT d.id, d.full_name, d.phone, 
               du.id as du_id, du.phone as du_phone, du.first_name as du_first_name, 
               du.last_name as du_last_name
        FROM drivers d
        LEFT JOIN driver_users du ON d.id = du.driver_id
        ORDER BY d.id;
    """)
    
    final_drivers = cursor.fetchall()
    
    print("\nРезультаты после исправления:")
    for driver in final_drivers:
        is_phone_synced = driver['phone'] == driver['du_phone']
        is_synced = is_phone_synced and driver['du_id'] is not None
        status = "✅ Синхронизировано" if is_synced else "❌ Не синхронизировано"
        
        print(f"ID: {driver['id']}, Имя: {driver['full_name']}, Телефон: {driver['phone']} / {driver['du_phone']} - {status}")
    
    # Итоги
    synced_count = sum(1 for d in final_drivers if 
                      d['phone'] == d['du_phone'] and 
                      d['du_id'] is not None)
    
    total_count = len(final_drivers)
    print(f"\nИтого: {synced_count} из {total_count} водителей имеют синхронизированные данные")

def fix_driver_deletion(cursor, driver_id):
    """Исправление связей перед удалением водителя"""
    print(f"\n🔧 Исправление связей для возможности удаления водителя ID={driver_id}...")
    
    # Проверка существования водителя
    cursor.execute("SELECT id, full_name FROM drivers WHERE id = %s", (driver_id,))
    driver = cursor.fetchone()
    if not driver:
        print(f"❌ Водитель с ID={driver_id} не найден")
        return False
    
    print(f"Подготовка к удалению водителя: {driver['full_name']} (ID: {driver['id']})")
    
    # Список таблиц для проверки связей
    relations = [
        {"table": "orders", "column": "driver_id", "action": "update_null"},
        {"table": "balance_transactions", "column": "driver_id", "action": "update_null"},
        {"table": "driver_users", "column": "driver_id", "action": "update_null"},
        {"table": "cars", "column": "driver_id", "action": "delete"},
        {"table": "messages", "column": "sender_id", "action": "update_null"},
        {"table": "messages", "column": "recipient_id", "action": "update_null"},
        {"table": "driver_cars", "column": "driver_id", "action": "delete"},
    ]
    
    total_fixed = 0
    
    # Обработка каждой таблицы
    for relation in relations:
        table = relation["table"]
        column = relation["column"]
        action = relation["action"]
        
        # Проверка наличия связанных записей
        query = f"SELECT COUNT(*) as count FROM {table} WHERE {column} = %s"
        cursor.execute(query, (driver_id,))
        count = cursor.fetchone()["count"]
        
        if count > 0:
            if action == "update_null":
                # Установка NULL для связанного поля
                try:
                    update_query = f"UPDATE {table} SET {column} = NULL WHERE {column} = %s"
                    cursor.execute(update_query, (driver_id,))
                    print(f"✅ В таблице {table} обновлено {count} записей (установлен NULL)")
                    total_fixed += count
                except Exception as e:
                    print(f"❌ Ошибка при обновлении записей в {table}: {e}")
            elif action == "delete":
                # Удаление связанных записей
                try:
                    delete_query = f"DELETE FROM {table} WHERE {column} = %s"
                    cursor.execute(delete_query, (driver_id,))
                    print(f"✅ Из таблицы {table} удалено {count} записей")
                    total_fixed += count
                except Exception as e:
                    print(f"❌ Ошибка при удалении записей из {table}: {e}")
    
    print(f"\nИсправлено связей: {total_fixed}")
    
    # Проверка возможности удаления
    try:
        cursor.execute("BEGIN")
        cursor.execute("DELETE FROM drivers WHERE id = %s", (driver_id,))
        cursor.execute("COMMIT")
        print(f"✅ Водитель успешно удален")
        return True
    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"❌ Не удалось удалить водителя: {e}")
        return False

def main():
    """Основная функция скрипта"""
    print("🔧 Запуск исправления синхронизации данных...")
    
    conn, cursor = connect_to_db()
    
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "delete_driver" and len(sys.argv) > 2:
            # Режим удаления водителя
            driver_id = int(sys.argv[2])
            fix_driver_deletion(cursor, driver_id)
        else:
            # Стандартный режим синхронизации
            fix_tariff_sync(cursor)
            fix_car_data_sync(cursor)
            fix_driver_data_sync(cursor)
            
            print("\n✅ Все операции по исправлению синхронизации данных выполнены!")
        
    except Exception as e:
        print(f"\n❌ Ошибка при выполнении операций: {e}")
    finally:
        close_connection(conn, cursor)

if __name__ == "__main__":
    main() 