#!/usr/bin/env python
# -*- coding: utf-8 -*-
import psycopg2
import psycopg2.extras
import json
import os
from tabulate import tabulate

# Настройки подключения к базе данных
DB_CONFIG = {
    'dbname': 'wazir',
    'user': 'postgres',
    'password': '123',
    'host': 'localhost',
    'port': '5432'
}

class DataSynchronizer:
    def __init__(self, config):
        self.config = config
        self.conn = None
        self.cursor = None
        self.synced_records = 0
        self.issues_found = 0

    def connect(self):
        """Подключение к базе данных PostgreSQL"""
        try:
            self.conn = psycopg2.connect(**self.config)
            self.conn.autocommit = True
            self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            print("✅ Успешное подключение к базе данных {} на {}:{}".format(
                self.config['dbname'], self.config['host'], self.config['port']))
            return True
        except psycopg2.Error as e:
            print("❌ Ошибка подключения к базе данных: {}".format(e))
            return False

    def close(self):
        """Закрытие подключения к базе данных"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        print("👋 Соединение с базой данных закрыто")

    def check_tariff_sync(self):
        """Проверка синхронизации тарифов между таблицами"""
        print("\n🔄 Проверка синхронизации тарифов...")
        
        self.cursor.execute("""
            SELECT d.id, d.full_name, d.tariff_id, d.tariff, t.name AS tariff_name
            FROM drivers d
            LEFT JOIN tariffs t ON d.tariff_id = t.id
            ORDER BY d.id;
        """)
        
        drivers = self.cursor.fetchall()
        
        if not drivers:
            print("⚠️ Нет данных о водителях")
            return
        
        issues = []
        for driver in drivers:
            # Проверяем соответствие tariff_id и tariff
            if driver['tariff_id'] is not None and driver['tariff'] is not None:
                if str(driver['tariff_id']) != str(driver['tariff']) and driver['tariff'] != driver['tariff_name']:
                    issues.append({
                        'driver_id': driver['id'],
                        'name': driver['full_name'],
                        'tariff_id': driver['tariff_id'],
                        'tariff': driver['tariff'],
                        'tariff_name': driver['tariff_name']
                    })
        
        if issues:
            print(f"⚠️ Найдено {len(issues)} проблем с синхронизацией тарифов:")
            table_data = []
            for issue in issues:
                table_data.append([
                    issue['driver_id'], 
                    issue['name'], 
                    issue['tariff_id'] or 'None', 
                    issue['tariff'] or 'None',
                    issue['tariff_name'] or 'None'
                ])
            
            print(tabulate(table_data, headers=["ID", "Имя", "ID тарифа", "Тариф", "Название тарифа"]))
            
            print("\nИсправление проблем синхронизации тарифов...")
            for issue in issues:
                try:
                    # Если есть tariff_id, обновляем tariff на основе tariff_name
                    if issue['tariff_id'] is not None and issue['tariff_name'] is not None:
                        self.cursor.execute("""
                            UPDATE drivers
                            SET tariff = %s
                            WHERE id = %s;
                        """, (issue['tariff_name'], issue['driver_id']))
                        print(f"✅ Обновлен тариф для водителя {issue['name']} (ID: {issue['driver_id']}): {issue['tariff']} -> {issue['tariff_name']}")
                    # Если нет tariff_id, но есть tariff, находим соответствующий tariff_id
                    elif issue['tariff'] is not None:
                        self.cursor.execute("""
                            SELECT id FROM tariffs
                            WHERE name = %s OR name ILIKE %s;
                        """, (issue['tariff'], f"%{issue['tariff']}%"))
                        
                        tariff_result = self.cursor.fetchone()
                        if tariff_result:
                            tariff_id = tariff_result['id']
                            self.cursor.execute("""
                                UPDATE drivers
                                SET tariff_id = %s
                                WHERE id = %s;
                            """, (tariff_id, issue['driver_id']))
                            print(f"✅ Обновлен ID тарифа для водителя {issue['name']} (ID: {issue['driver_id']}): {issue['tariff_id']} -> {tariff_id}")
                        else:
                            print(f"⚠️ Не найден тариф с названием '{issue['tariff']}' в таблице тарифов")
                    self.synced_records += 1
                except psycopg2.Error as e:
                    print(f"❌ Ошибка при обновлении тарифа для водителя {issue['driver_id']}: {e}")
            
            self.issues_found += len(issues)
        else:
            print("✅ Тарифы синхронизированы корректно")
    
    def check_car_sync(self):
        """Проверка синхронизации данных автомобилей между cars и driver_cars"""
        print("\n🔄 Проверка синхронизации данных автомобилей...")
        
        self.cursor.execute("""
            SELECT c.id AS car_id, c.driver_id, c.brand, c.model, c.license_plate, 
                   c.year, c.color, c.status,
                   dc.id AS dc_id, dc.driver_id AS dc_driver_id, dc.brand AS dc_brand, 
                   dc.model AS dc_model, dc.license_plate AS dc_license_plate,
                   dc.year AS dc_year, dc.color AS dc_color, dc.status AS dc_status
            FROM cars c
            LEFT JOIN driver_cars dc ON c.driver_id = dc.driver_id
            ORDER BY c.driver_id;
        """)
        
        cars = self.cursor.fetchall()
        
        if not cars:
            print("⚠️ Нет данных об автомобилях")
            return
        
        issues = []
        for car in cars:
            # Проверяем наличие соответствующей записи в driver_cars
            if car['dc_id'] is None:
                issues.append({
                    'type': 'missing',
                    'car_id': car['car_id'],
                    'driver_id': car['driver_id'],
                    'data': car
                })
            # Проверяем соответствие данных между cars и driver_cars
            elif (car['brand'] != car['dc_brand'] or 
                  car['model'] != car['dc_model'] or 
                  car['license_plate'] != car['dc_license_plate'] or
                  car['year'] != car['dc_year'] or
                  car['color'] != car['dc_color'] or
                  car['status'] != car['dc_status']):
                issues.append({
                    'type': 'mismatch',
                    'car_id': car['car_id'],
                    'dc_id': car['dc_id'],
                    'driver_id': car['driver_id'],
                    'data': car
                })
        
        if issues:
            print(f"⚠️ Найдено {len(issues)} проблем с синхронизацией данных автомобилей:")
            missing_count = len([i for i in issues if i['type'] == 'missing'])
            mismatch_count = len([i for i in issues if i['type'] == 'mismatch'])
            print(f"  - Отсутствующие записи в driver_cars: {missing_count}")
            print(f"  - Несоответствия данных: {mismatch_count}")
            
            print("\nИсправление проблем синхронизации автомобилей...")
            for issue in issues:
                try:
                    if issue['type'] == 'missing':
                        # Создаем запись в driver_cars на основе данных из cars
                        car = issue['data']
                        self.cursor.execute("""
                            INSERT INTO driver_cars (driver_id, brand, model, license_plate, year, color, status)
                            VALUES (%s, %s, %s, %s, %s, %s, %s);
                        """, (
                            car['driver_id'], car['brand'], car['model'], 
                            car['license_plate'], car['year'], car['color'], car['status']
                        ))
                        print(f"✅ Создана запись в driver_cars для автомобиля ID: {car['car_id']} (водитель ID: {car['driver_id']})")
                    elif issue['type'] == 'mismatch':
                        # Обновляем данные в driver_cars в соответствии с cars
                        car = issue['data']
                        self.cursor.execute("""
                            UPDATE driver_cars
                            SET brand = %s, model = %s, license_plate = %s, 
                                year = %s, color = %s, status = %s
                            WHERE id = %s;
                        """, (
                            car['brand'], car['model'], car['license_plate'],
                            car['year'], car['color'], car['status'], car['dc_id']
                        ))
                        print(f"✅ Обновлены данные в driver_cars для автомобиля ID: {car['car_id']} (driver_cars ID: {car['dc_id']})")
                    self.synced_records += 1
                except psycopg2.Error as e:
                    print(f"❌ Ошибка при синхронизации данных автомобиля {issue['car_id']}: {e}")
            
            self.issues_found += len(issues)
        else:
            print("✅ Данные автомобилей синхронизированы корректно")
    
    def check_driver_sync(self):
        """Проверка синхронизации данных водителей между drivers и driver_users"""
        print("\n🔄 Проверка синхронизации данных водителей...")
        
        self.cursor.execute("""
            SELECT d.id AS driver_id, d.full_name, d.phone, d.status, d.first_name, d.last_name,
                   du.id AS du_id, du.driver_id AS du_driver_id, du.phone AS du_phone, 
                   du.first_name AS du_first_name, du.last_name AS du_last_name
            FROM drivers d
            LEFT JOIN driver_users du ON d.id = du.driver_id
            ORDER BY d.id;
        """)
        
        drivers = self.cursor.fetchall()
        
        if not drivers:
            print("⚠️ Нет данных о водителях")
            return
        
        issues = []
        for driver in drivers:
            # Проверяем наличие соответствующей записи в driver_users
            if driver['du_id'] is None:
                issues.append({
                    'type': 'missing',
                    'driver_id': driver['driver_id'],
                    'data': driver
                })
            # Проверяем соответствие основных данных
            elif (driver['phone'] != driver['du_phone'] or
                  (driver['first_name'] is not None and driver['du_first_name'] is not None and 
                   driver['first_name'] != driver['du_first_name']) or
                  (driver['last_name'] is not None and driver['du_last_name'] is not None and 
                   driver['last_name'] != driver['du_last_name'])):
                issues.append({
                    'type': 'mismatch',
                    'driver_id': driver['driver_id'],
                    'du_id': driver['du_id'],
                    'data': driver
                })
        
        if issues:
            print(f"⚠️ Найдено {len(issues)} проблем с синхронизацией данных водителей:")
            missing_count = len([i for i in issues if i['type'] == 'missing'])
            mismatch_count = len([i for i in issues if i['type'] == 'mismatch'])
            print(f"  - Отсутствующие записи в driver_users: {missing_count}")
            print(f"  - Несоответствия данных: {mismatch_count}")
            
            print("\nИсправление проблем синхронизации данных водителей...")
            for issue in issues:
                try:
                    if issue['type'] == 'missing':
                        # Создаем запись в driver_users на основе данных из drivers
                        driver = issue['data']
                        # Генерируем хэш пароля по умолчанию
                        default_password = "pbkdf2:sha256:150000$" + "defaultpassword"
                        first_name = driver['first_name'] or (driver['full_name'].split()[0] if driver['full_name'] else "")
                        last_name = driver['last_name'] or (driver['full_name'].split()[1] if driver['full_name'] and len(driver['full_name'].split()) > 1 else "")
                        
                        self.cursor.execute("""
                            INSERT INTO driver_users (driver_id, phone, password, first_name, last_name)
                            VALUES (%s, %s, %s, %s, %s);
                        """, (
                            driver['driver_id'], driver['phone'], default_password, first_name, last_name
                        ))
                        print(f"✅ Создана запись в driver_users для водителя ID: {driver['driver_id']}")
                    elif issue['type'] == 'mismatch':
                        # Обновляем данные в driver_users в соответствии с drivers
                        driver = issue['data']
                        updates = []
                        params = []
                        
                        if driver['phone'] != driver['du_phone']:
                            updates.append("phone = %s")
                            params.append(driver['phone'])
                        
                        if driver['first_name'] and driver['first_name'] != driver.get('du_first_name'):
                            updates.append("first_name = %s")
                            params.append(driver['first_name'])
                        
                        if driver['last_name'] and driver['last_name'] != driver.get('du_last_name'):
                            updates.append("last_name = %s")
                            params.append(driver['last_name'])
                        
                        if updates:
                            query = f"""
                                UPDATE driver_users
                                SET {", ".join(updates)}
                                WHERE id = %s;
                            """
                            params.append(driver['du_id'])
                            self.cursor.execute(query, tuple(params))
                            print(f"✅ Обновлены данные в driver_users для водителя ID: {driver['driver_id']}")
                    self.synced_records += 1
                except psycopg2.Error as e:
                    print(f"❌ Ошибка при синхронизации данных водителя {issue['driver_id']}: {e}")
            
            self.issues_found += len(issues)
        else:
            print("✅ Данные водителей синхронизированы корректно")
    
    def check_order_sync(self):
        """Проверка данных заказов и их статусов"""
        print("\n🔄 Проверка данных заказов...")
        
        self.cursor.execute("""
            SELECT id, time, origin, destination, driver_id, status, price, payment_method
            FROM orders
            ORDER BY id;
        """)
        
        orders = self.cursor.fetchall()
        
        if not orders:
            print("⚠️ Нет данных о заказах")
            return
        
        issues = []
        for order in orders:
            # Проверяем корректность данных заказа
            problems = []
            
            if order['status'] not in ('new', 'accepted', 'completed', 'cancelled'):
                problems.append(f"Некорректный статус: {order['status']}")
            
            if order['driver_id'] is not None and order['status'] == 'new':
                problems.append(f"Статус 'new', но назначен водитель: {order['driver_id']}")
            
            if order['driver_id'] is None and order['status'] in ('accepted', 'completed'):
                problems.append(f"Статус '{order['status']}', но нет водителя")
            
            if order['price'] is None and order['status'] == 'completed':
                problems.append("Заказ завершен, но нет цены")
            
            if problems:
                issues.append({
                    'order_id': order['id'],
                    'problems': problems,
                    'data': order
                })
        
        if issues:
            print(f"⚠️ Найдено {len(issues)} проблем с данными заказов:")
            for issue in issues:
                print(f"  Заказ ID: {issue['order_id']}")
                for problem in issue['problems']:
                    print(f"    - {problem}")
            
            print("\nИсправление проблем с данными заказов...")
            for issue in issues:
                try:
                    order = issue['data']
                    updates = []
                    params = []
                    
                    # Исправление статуса
                    if any("Некорректный статус" in p for p in issue['problems']):
                        updates.append("status = %s")
                        params.append('new')
                    
                    # Исправление несоответствия между статусом и водителем
                    if any("Статус 'new', но назначен водитель" in p for p in issue['problems']):
                        updates.append("status = %s")
                        params.append('accepted')
                    
                    if any("Статус 'accepted' или 'completed', но нет водителя" in p for p in issue['problems']):
                        # Найдем доступного водителя
                        self.cursor.execute("""
                            SELECT id FROM drivers
                            WHERE status = 'active'
                            ORDER BY id
                            LIMIT 1;
                        """)
                        driver_result = self.cursor.fetchone()
                        if driver_result:
                            updates.append("driver_id = %s")
                            params.append(driver_result['id'])
                    
                    # Исправление цены для завершенных заказов
                    if any("Заказ завершен, но нет цены" in p for p in issue['problems']):
                        updates.append("price = %s")
                        params.append(500)  # Значение по умолчанию
                    
                    if updates:
                        query = f"""
                            UPDATE orders
                            SET {", ".join(updates)}
                            WHERE id = %s;
                        """
                        params.append(order['id'])
                        self.cursor.execute(query, tuple(params))
                        print(f"✅ Обновлены данные заказа ID: {order['id']}")
                        self.synced_records += 1
                except psycopg2.Error as e:
                    print(f"❌ Ошибка при исправлении данных заказа {issue['order_id']}: {e}")
            
            self.issues_found += len(issues)
        else:
            print("✅ Данные заказов корректны")

    def fix_all_sync_issues(self):
        """Запуск всех проверок и исправлений синхронизации данных"""
        print("🔧 Запуск проверки и исправления синхронизации данных между частями приложения...")
        
        if not self.connect():
            return False
        
        try:
            # Проверка и исправление синхронизации различных данных
            self.check_tariff_sync()
            self.check_car_sync()
            self.check_driver_sync()
            self.check_order_sync()
            
            # Итоговая статистика
            print("\n📊 Итоги синхронизации:")
            print(f"  Найдено проблем: {self.issues_found}")
            print(f"  Исправлено записей: {self.synced_records}")
            
            if self.issues_found == 0:
                print("\n✅ Данные полностью синхронизированы между всеми частями приложения!")
            elif self.synced_records == self.issues_found:
                print("\n✅ Все проблемы синхронизации успешно исправлены!")
            else:
                print(f"\n⚠️ Исправлено {self.synced_records} из {self.issues_found} проблем синхронизации")
                print("   Для проверки оставшихся проблем запустите скрипт повторно")
            
            return True
        except Exception as e:
            print(f"❌ Ошибка при выполнении операций: {e}")
            return False
        finally:
            self.close()

def main():
    """Основная функция запуска скрипта"""
    synchronizer = DataSynchronizer(DB_CONFIG)
    synchronizer.fix_all_sync_issues()

if __name__ == "__main__":
    main() 