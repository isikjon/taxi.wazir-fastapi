#!/usr/bin/env python
# -*- coding: utf-8 -*-
import psycopg2
import psycopg2.extras
import random
import string
import datetime

# Настройки подключения к базе данных
DB_CONFIG = {
    'dbname': 'wazir',
    'user': 'postgres',
    'password': '123',
    'host': 'localhost',
    'port': '5432'
}

class NullValueFixer:
    def __init__(self, config):
        self.config = config
        self.conn = None
        self.cursor = None

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

    def generate_random_phone(self):
        """Генерация случайного номера телефона"""
        return "+7" + "".join(random.choices(string.digits, k=10))

    def generate_random_name(self):
        """Генерация случайного имени"""
        first_names = ["Александр", "Иван", "Дмитрий", "Сергей", "Михаил", "Андрей", "Николай", "Петр", "Виктор", "Максим"]
        last_names = ["Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", "Новиков", "Федоров"]
        return f"{random.choice(first_names)} {random.choice(last_names)}"

    def generate_random_car_brand(self):
        """Генерация случайной марки автомобиля"""
        brands = ["Toyota", "Honda", "Ford", "Volkswagen", "BMW", "Mercedes", "Audi", "Hyundai", "Kia", "Nissan"]
        return random.choice(brands)

    def generate_random_car_model(self):
        """Генерация случайной модели автомобиля"""
        models = ["Camry", "Civic", "Focus", "Golf", "X5", "E-Class", "A4", "Sonata", "Sportage", "Altima"]
        return random.choice(models)

    def generate_random_license_plate(self):
        """Генерация случайного номера автомобиля"""
        letters = "АВЕКМНОРСТУХ"
        region_codes = ["77", "78", "50", "47", "99", "197", "177", "97", "777", "799"]
        plate = random.choice(letters) + random.choice(string.digits) + random.choice(string.digits) + random.choice(string.digits) + random.choice(letters) + random.choice(letters)
        region = random.choice(region_codes)
        return f"{plate}{region}"

    def generate_random_date(self, start_year=2010, end_year=2023):
        """Генерация случайной даты"""
        year = random.randint(start_year, end_year)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        return datetime.date(year, month, day)

    def fix_null_values_in_drivers(self):
        """Заполнение NULL-значений в таблице drivers"""
        print("\n🔍 Поиск и заполнение NULL-значений в таблице drivers...")
        
        # Получаем список столбцов таблицы drivers
        self.cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'drivers'
            ORDER BY ordinal_position;
        """)
        
        columns = self.cursor.fetchall()
        column_names = [col['column_name'] for col in columns]
        
        # Получаем записи с NULL-значениями
        query_parts = []
        for col in column_names:
            query_parts.append(f"{col} IS NULL")
        
        null_check_query = " OR ".join(query_parts)
        
        self.cursor.execute(f"""
            SELECT id, {', '.join(column_names)}
            FROM drivers
            WHERE {null_check_query};
        """)
        
        drivers_with_nulls = self.cursor.fetchall()
        fixed_count = 0
        
        if not drivers_with_nulls:
            print("✅ В таблице drivers нет NULL-значений")
            return fixed_count
        
        print(f"⚠️ Найдено {len(drivers_with_nulls)} записей с NULL-значениями в таблице drivers")
        
        # Обновляем каждую запись с NULL-значениями
        for driver in drivers_with_nulls:
            updates = {}
            
            # Определяем, какие поля нужно обновить
            for col in column_names:
                if driver[col] is None:
                    if col == 'full_name':
                        updates[col] = self.generate_random_name()
                    elif col == 'phone':
                        updates[col] = self.generate_random_phone()
                    elif col == 'status':
                        updates[col] = random.choice(['active', 'inactive', 'pending'])
                    elif col == 'balance':
                        updates[col] = round(random.uniform(0, 10000), 2)
                    elif col == 'date_registered':
                        updates[col] = self.generate_random_date()
                    elif col == 'is_verified':
                        updates[col] = random.choice([True, False])
                    elif col == 'rating':
                        updates[col] = round(random.uniform(3.0, 5.0), 1)
                    elif col == 'first_name':
                        first_name = self.generate_random_name().split()[0]
                        updates[col] = first_name
                    elif col == 'last_name':
                        last_name = self.generate_random_name().split()[1]
                        updates[col] = last_name
            
            if not updates:
                continue
            
            # Формируем SQL запрос для обновления
            set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
            values = list(updates.values())
            
            try:
                self.cursor.execute(f"""
                    UPDATE drivers
                    SET {set_clause}
                    WHERE id = %s;
                """, values + [driver['id']])
                
                fixed_count += 1
                print(f"✅ Обновлена запись с id={driver['id']}: {', '.join([f'{k}={v}' for k, v in updates.items()])}")
            except psycopg2.Error as e:
                print(f"❌ Ошибка обновления записи с id={driver['id']}: {e}")
        
        print(f"✅ Обновлено {fixed_count} из {len(drivers_with_nulls)} записей в таблице drivers")
        return fixed_count

    def fix_null_values_in_driver_users(self):
        """Заполнение NULL-значений в таблице driver_users"""
        print("\n🔍 Поиск и заполнение NULL-значений в таблице driver_users...")
        
        # Получаем список столбцов таблицы driver_users
        self.cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'driver_users'
            ORDER BY ordinal_position;
        """)
        
        columns = self.cursor.fetchall()
        column_names = [col['column_name'] for col in columns]
        
        # Получаем записи с NULL-значениями
        query_parts = []
        for col in column_names:
            query_parts.append(f"{col} IS NULL")
        
        null_check_query = " OR ".join(query_parts)
        
        self.cursor.execute(f"""
            SELECT id, {', '.join(column_names)}
            FROM driver_users
            WHERE {null_check_query};
        """)
        
        users_with_nulls = self.cursor.fetchall()
        fixed_count = 0
        
        if not users_with_nulls:
            print("✅ В таблице driver_users нет NULL-значений")
            return fixed_count
        
        print(f"⚠️ Найдено {len(users_with_nulls)} записей с NULL-значениями в таблице driver_users")
        
        # Обновляем каждую запись с NULL-значениями
        for user in users_with_nulls:
            updates = {}
            
            # Определяем, какие поля нужно обновить
            for col in column_names:
                if user[col] is None:
                    if col == 'phone':
                        updates[col] = self.generate_random_phone()
                    elif col == 'password':
                        updates[col] = 'pbkdf2:sha256:150000$' + ''.join(random.choices(string.ascii_letters + string.digits, k=20))
                    elif col == 'first_name':
                        updates[col] = self.generate_random_name().split()[0]
                    elif col == 'last_name':
                        updates[col] = self.generate_random_name().split()[1]
                    elif col == 'email':
                        updates[col] = f"user{random.randint(1000, 9999)}@example.com"
                    elif col == 'is_verified':
                        updates[col] = random.choice([True, False])
            
            if not updates:
                continue
            
            # Формируем SQL запрос для обновления
            set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
            values = list(updates.values())
            
            try:
                self.cursor.execute(f"""
                    UPDATE driver_users
                    SET {set_clause}
                    WHERE id = %s;
                """, values + [user['id']])
                
                fixed_count += 1
                print(f"✅ Обновлена запись с id={user['id']}: {', '.join([f'{k}={v}' for k, v in updates.items()])}")
            except psycopg2.Error as e:
                print(f"❌ Ошибка обновления записи с id={user['id']}: {e}")
        
        print(f"✅ Обновлено {fixed_count} из {len(users_with_nulls)} записей в таблице driver_users")
        return fixed_count

    def fix_null_values_in_cars(self):
        """Заполнение NULL-значений в таблицах cars и driver_cars"""
        print("\n🔍 Поиск и заполнение NULL-значений в таблицах cars и driver_cars...")
        
        tables = ['cars', 'driver_cars']
        total_fixed = 0
        
        for table_name in tables:
            # Получаем список столбцов таблицы
            self.cursor.execute(f"""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """)
            
            columns = self.cursor.fetchall()
            column_names = [col['column_name'] for col in columns]
            
            # Получаем записи с NULL-значениями
            query_parts = []
            for col in column_names:
                query_parts.append(f"{col} IS NULL")
            
            null_check_query = " OR ".join(query_parts)
            
            self.cursor.execute(f"""
                SELECT id, {', '.join(column_names)}
                FROM {table_name}
                WHERE {null_check_query};
            """)
            
            cars_with_nulls = self.cursor.fetchall()
            fixed_count = 0
            
            if not cars_with_nulls:
                print(f"✅ В таблице {table_name} нет NULL-значений")
                continue
            
            print(f"⚠️ Найдено {len(cars_with_nulls)} записей с NULL-значениями в таблице {table_name}")
            
            # Обновляем каждую запись с NULL-значениями
            for car in cars_with_nulls:
                updates = {}
                
                # Определяем, какие поля нужно обновить
                for col in column_names:
                    if car[col] is None:
                        if col == 'brand':
                            updates[col] = self.generate_random_car_brand()
                        elif col == 'model':
                            updates[col] = self.generate_random_car_model()
                        elif col == 'year':
                            updates[col] = random.randint(2010, 2023)
                        elif col == 'color':
                            updates[col] = random.choice(['Белый', 'Черный', 'Серебристый', 'Красный', 'Синий', 'Зеленый'])
                        elif col == 'license_plate':
                            updates[col] = self.generate_random_license_plate()
                        elif col == 'vin':
                            updates[col] = ''.join(random.choices(string.ascii_uppercase + string.digits, k=17))
                        elif col == 'registration_date':
                            updates[col] = self.generate_random_date()
                        elif col == 'status':
                            updates[col] = random.choice(['active', 'inactive', 'pending'])
                
                if not updates:
                    continue
                
                # Формируем SQL запрос для обновления
                set_clause = ", ".join([f"{key} = %s" for key in updates.keys()])
                values = list(updates.values())
                
                try:
                    self.cursor.execute(f"""
                        UPDATE {table_name}
                        SET {set_clause}
                        WHERE id = %s;
                    """, values + [car['id']])
                    
                    fixed_count += 1
                    print(f"✅ Обновлена запись с id={car['id']} в таблице {table_name}: {', '.join([f'{k}={v}' for k, v in updates.items()])}")
                except psycopg2.Error as e:
                    print(f"❌ Ошибка обновления записи с id={car['id']} в таблице {table_name}: {e}")
            
            print(f"✅ Обновлено {fixed_count} из {len(cars_with_nulls)} записей в таблице {table_name}")
            total_fixed += fixed_count
        
        return total_fixed

    def run_all_fixes(self):
        """Запуск всех операций по заполнению NULL-значений"""
        print("🔧 Запуск операций по заполнению NULL-значений в базе данных...")
        
        if not self.connect():
            return
        
        try:
            total_fixed = 0
            
            # Заполняем NULL-значения в таблицах
            total_fixed += self.fix_null_values_in_drivers()
            total_fixed += self.fix_null_values_in_driver_users()
            total_fixed += self.fix_null_values_in_cars()
            
            print(f"\n✅ Всего обновлено {total_fixed} записей с NULL-значениями")
            
        except Exception as e:
            print(f"❌ Ошибка при выполнении операций: {e}")
        finally:
            self.close()

def main():
    """Основная функция запуска скрипта"""
    fixer = NullValueFixer(DB_CONFIG)
    fixer.run_all_fixes()

if __name__ == "__main__":
    main() 