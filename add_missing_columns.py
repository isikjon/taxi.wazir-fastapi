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

class ColumnAdder:
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

    def get_table_columns(self, table_name):
        """Получение списка существующих столбцов в таблице"""
        self.cursor.execute(f"""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
        """)
        return {row['column_name']: {'type': row['data_type'], 'length': row['character_maximum_length']} 
                for row in self.cursor.fetchall()}

    def add_missing_columns_to_drivers(self):
        """Добавление недостающих столбцов в таблицу drivers"""
        print("\n🔧 Анализ и добавление недостающих столбцов в таблицу drivers...")
        
        # Получаем текущие столбцы
        current_columns = self.get_table_columns('drivers')
        print(f"📋 Текущие столбцы: {', '.join(current_columns.keys())}")
        
        # Определяем необходимые столбцы
        required_columns = {
            'driver_license_number': {'type': 'VARCHAR', 'default': None},
            'driver_license_issue_date': {'type': 'DATE', 'default': None},
            'birth_date': {'type': 'DATE', 'default': None},
            'callsign': {'type': 'VARCHAR', 'default': None},
            'city': {'type': 'VARCHAR', 'default': None},
            'tariff': {'type': 'VARCHAR', 'default': None},
            'taxi_park': {'type': 'VARCHAR', 'default': None},
            'activity': {'type': 'VARCHAR', 'default': None},
            'unique_id': {'type': 'VARCHAR', 'default': None},
        }
        
        # Добавляем недостающие столбцы
        added_columns = 0
        for col_name, col_info in required_columns.items():
            if col_name not in current_columns:
                default_clause = f"DEFAULT '{col_info['default']}'" if col_info['default'] else ""
                try:
                    self.cursor.execute(f"""
                        ALTER TABLE drivers 
                        ADD COLUMN {col_name} {col_info['type']} {default_clause};
                    """)
                    print(f"✅ Добавлен столбец {col_name} типа {col_info['type']} в таблицу drivers")
                    added_columns += 1
                except psycopg2.Error as e:
                    print(f"❌ Ошибка при добавлении столбца {col_name}: {e}")
        
        if added_columns == 0:
            print("✅ Все необходимые столбцы уже существуют в таблице drivers")
        else:
            print(f"✅ Добавлено {added_columns} столбцов в таблицу drivers")
        
        return added_columns

    def add_missing_columns_to_orders(self):
        """Добавление недостающих столбцов в таблицу orders"""
        print("\n🔧 Анализ и добавление недостающих столбцов в таблицу orders...")
        
        # Получаем текущие столбцы
        current_columns = self.get_table_columns('orders')
        print(f"📋 Текущие столбцы: {', '.join(current_columns.keys())}")
        
        # Определяем необходимые столбцы
        required_columns = {
            'payment_method': {'type': 'VARCHAR', 'default': 'cash'},
            'price': {'type': 'NUMERIC', 'default': 0},
            'notes': {'type': 'TEXT', 'default': None},
        }
        
        # Добавляем недостающие столбцы
        added_columns = 0
        for col_name, col_info in required_columns.items():
            if col_name not in current_columns:
                default_clause = f"DEFAULT '{col_info['default']}'" if col_info['default'] is not None else ""
                try:
                    self.cursor.execute(f"""
                        ALTER TABLE orders 
                        ADD COLUMN {col_name} {col_info['type']} {default_clause};
                    """)
                    print(f"✅ Добавлен столбец {col_name} типа {col_info['type']} в таблицу orders")
                    added_columns += 1
                except psycopg2.Error as e:
                    print(f"❌ Ошибка при добавлении столбца {col_name}: {e}")
        
        if added_columns == 0:
            print("✅ Все необходимые столбцы уже существуют в таблице orders")
        else:
            print(f"✅ Добавлено {added_columns} столбцов в таблицу orders")
        
        return added_columns

    def add_missing_columns_to_cars(self):
        """Добавление недостающих столбцов в таблицу cars"""
        print("\n🔧 Анализ и добавление недостающих столбцов в таблицу cars...")
        
        # Получаем текущие столбцы
        current_columns = self.get_table_columns('cars')
        print(f"📋 Текущие столбцы: {', '.join(current_columns.keys())}")
        
        # Определяем необходимые столбцы
        required_columns = {
            'vin': {'type': 'VARCHAR', 'default': None},
            'registration_date': {'type': 'DATE', 'default': None},
            'status': {'type': 'VARCHAR', 'default': 'active'},
        }
        
        # Добавляем недостающие столбцы
        added_columns = 0
        for col_name, col_info in required_columns.items():
            if col_name not in current_columns:
                default_clause = f"DEFAULT '{col_info['default']}'" if col_info['default'] is not None else ""
                try:
                    self.cursor.execute(f"""
                        ALTER TABLE cars 
                        ADD COLUMN {col_name} {col_info['type']} {default_clause};
                    """)
                    print(f"✅ Добавлен столбец {col_name} типа {col_info['type']} в таблицу cars")
                    added_columns += 1
                except psycopg2.Error as e:
                    print(f"❌ Ошибка при добавлении столбца {col_name}: {e}")
        
        if added_columns == 0:
            print("✅ Все необходимые столбцы уже существуют в таблице cars")
        else:
            print(f"✅ Добавлено {added_columns} столбцов в таблицу cars")
        
        return added_columns

    def add_missing_columns_to_driver_users(self):
        """Добавление недостающих столбцов в таблицу driver_users"""
        print("\n🔧 Анализ и добавление недостающих столбцов в таблицу driver_users...")
        
        # Получаем текущие столбцы
        current_columns = self.get_table_columns('driver_users')
        print(f"📋 Текущие столбцы: {', '.join(current_columns.keys())}")
        
        # Определяем необходимые столбцы
        required_columns = {
            'email': {'type': 'VARCHAR', 'default': None},
            'is_verified': {'type': 'BOOLEAN', 'default': 'false'},
        }
        
        # Добавляем недостающие столбцы
        added_columns = 0
        for col_name, col_info in required_columns.items():
            if col_name not in current_columns:
                default_clause = f"DEFAULT {col_info['default']}" if col_info['default'] is not None else ""
                try:
                    self.cursor.execute(f"""
                        ALTER TABLE driver_users 
                        ADD COLUMN {col_name} {col_info['type']} {default_clause};
                    """)
                    print(f"✅ Добавлен столбец {col_name} типа {col_info['type']} в таблицу driver_users")
                    added_columns += 1
                except psycopg2.Error as e:
                    print(f"❌ Ошибка при добавлении столбца {col_name}: {e}")
        
        if added_columns == 0:
            print("✅ Все необходимые столбцы уже существуют в таблице driver_users")
        else:
            print(f"✅ Добавлено {added_columns} столбцов в таблицу driver_users")
        
        return added_columns

    def run(self):
        """Запуск всех операций по добавлению столбцов"""
        print("🔧 Запуск операций по добавлению недостающих столбцов в таблицы базы данных...")
        
        if not self.connect():
            return
        
        try:
            total_added = 0
            
            # Добавляем столбцы в таблицы
            total_added += self.add_missing_columns_to_drivers()
            total_added += self.add_missing_columns_to_orders()
            total_added += self.add_missing_columns_to_cars()
            total_added += self.add_missing_columns_to_driver_users()
            
            print(f"\n✅ Всего добавлено {total_added} недостающих столбцов в таблицы базы данных")
            
        except Exception as e:
            print(f"❌ Ошибка при выполнении операций: {e}")
        finally:
            self.close()

def main():
    """Основная функция запуска скрипта"""
    adder = ColumnAdder(DB_CONFIG)
    adder.run()

if __name__ == "__main__":
    main() 