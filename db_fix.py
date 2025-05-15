#!/usr/bin/env python
# -*- coding: utf-8 -*-
import psycopg2
import psycopg2.extras
import sys
import time
from tabulate import tabulate

# Настройки подключения к базе данных
DB_CONFIG = {
    'dbname': 'wazir',
    'user': 'postgres',
    'password': '123',
    'host': 'localhost',
    'port': '5432'
}

class DatabaseFixer:
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

    def fix_missing_foreign_key_indexes(self):
        """Поиск и создание недостающих индексов для внешних ключей"""
        print("\n🔍 Поиск внешних ключей без индексов...")
        
        # SQL запрос для поиска внешних ключей без индексов
        self.cursor.execute("""
            WITH fk_constraints AS (
                SELECT
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_name AS foreign_table_name,
                    tc.constraint_name
                FROM
                    information_schema.table_constraints tc
                JOIN
                    information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN
                    information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                    AND tc.table_schema = ccu.table_schema
                WHERE
                    tc.constraint_type = 'FOREIGN KEY'
                    AND tc.table_schema = 'public'
            ),
            all_indexes AS (
                SELECT
                    t.relname AS table_name,
                    a.attname AS column_name,
                    ix.relname AS index_name
                FROM
                    pg_class t
                JOIN
                    pg_index i ON t.oid = i.indrelid
                JOIN
                    pg_class ix ON ix.oid = i.indexrelid
                JOIN
                    pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(i.indkey)
                JOIN
                    pg_namespace n ON n.oid = t.relnamespace
                WHERE
                    t.relkind = 'r'
                    AND n.nspname = 'public'
            )
            SELECT
                fk.table_name,
                fk.column_name,
                fk.foreign_table_name,
                fk.constraint_name,
                i.index_name
            FROM
                fk_constraints fk
            LEFT JOIN
                all_indexes i ON i.table_name = fk.table_name AND i.column_name = fk.column_name
            WHERE
                i.index_name IS NULL
            ORDER BY
                fk.table_name, fk.column_name;
        """)
        
        missing_indexes = self.cursor.fetchall()
        
        if not missing_indexes:
            print("✅ Все внешние ключи имеют соответствующие индексы!")
            return
        
        # Вывод найденных внешних ключей без индексов
        print("\n⚠️ Найдено {} внешних ключей без индексов:".format(len(missing_indexes)))
        table_data = []
        for row in missing_indexes:
            table_data.append([row['table_name'], row['column_name'], 
                              row['foreign_table_name'], row['constraint_name']])
        
        print(tabulate(table_data, headers=["Таблица", "Столбец", "Ссылка", "Имя ограничения"]))
        
        print("\nСоздание индексов...")
        created_indexes = 0
        
        # Создание индексов для найденных внешних ключей
        for row in missing_indexes:
            table_name = row['table_name']
            column_name = row['column_name']
            index_name = f"idx_{table_name}_{column_name}"
            
            try:
                self.cursor.execute(f"""
                    CREATE INDEX {index_name} ON {table_name} ({column_name});
                """)
                print(f"✅ Создан индекс {index_name} для {table_name}.{column_name}")
                created_indexes += 1
            except psycopg2.Error as e:
                print(f"❌ Ошибка создания индекса для {table_name}.{column_name}: {e}")
        
        print(f"✅ Создание индексов завершено ({created_indexes} из {len(missing_indexes)})")

    def find_tables_without_pk(self):
        """Поиск таблиц без первичных ключей"""
        print("\n🔍 Поиск таблиц без первичных ключей...")
        
        self.cursor.execute("""
            SELECT 
                c.relname AS table_name
            FROM 
                pg_class c
            JOIN 
                pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN 
                pg_constraint con ON con.conrelid = c.oid AND con.contype = 'p'
            WHERE 
                c.relkind = 'r' AND
                n.nspname = 'public' AND
                con.conname IS NULL
            ORDER BY 
                c.relname;
        """)
        
        tables_without_pk = self.cursor.fetchall()
        
        if not tables_without_pk:
            print("✅ Все таблицы имеют первичные ключи!")
            return
        
        print(f"\n⚠️ Найдено {len(tables_without_pk)} таблиц без первичных ключей:")
        for row in tables_without_pk:
            table_name = row['table_name']
            print(f"  - {table_name}")
            
            # Получаем список столбцов для таблицы
            self.cursor.execute(f"""
                SELECT 
                    column_name, data_type
                FROM 
                    information_schema.columns
                WHERE 
                    table_schema = 'public' AND
                    table_name = '{table_name}'
                ORDER BY 
                    ordinal_position;
            """)
            
            columns = self.cursor.fetchall()
            possible_pk_columns = []
            
            # Поиск столбцов-кандидатов для PK
            for col in columns:
                col_name = col['column_name']
                if col_name in ('id', f"{table_name}_id", f"{table_name.rstrip('s')}_id"):
                    possible_pk_columns.append(col_name)
            
            if possible_pk_columns:
                print(f"    Рекомендуемые столбцы для PK: {', '.join(possible_pk_columns)}")
                print(f"    Для создания PK выполните: ALTER TABLE {table_name} ADD PRIMARY KEY ({possible_pk_columns[0]});")
            else:
                print(f"    Не найдены подходящие столбцы для PK. Рассмотрите добавление столбца id")

    def vacuum_analyze(self):
        """Выполнение VACUUM ANALYZE для оптимизации базы данных"""
        print("\n🧹 Выполнение VACUUM ANALYZE...")
        
        # Получаем список всех таблиц
        self.cursor.execute("""
            SELECT 
                tablename 
            FROM 
                pg_tables 
            WHERE 
                schemaname = 'public'
            ORDER BY 
                tablename;
        """)
        
        tables = self.cursor.fetchall()
        
        # VACUUM ANALYZE для каждой таблицы
        total_tables = len(tables)
        for i, row in enumerate(tables, 1):
            table_name = row['tablename']
            progress = f"[{i}/{total_tables}]"
            try:
                print(f"{progress} Выполнение VACUUM ANALYZE для {table_name}...", end="")
                # Отключаем autocommit для VACUUM
                old_isolation = self.conn.isolation_level
                self.conn.set_isolation_level(0)
                self.cursor.execute(f"VACUUM ANALYZE {table_name};")
                self.conn.set_isolation_level(old_isolation)
                print(" ✓")
            except psycopg2.Error as e:
                print(f" ❌ Ошибка: {e}")
        
        print("✅ VACUUM ANALYZE выполнен для всех таблиц")

    def check_sequences(self):
        """Проверка и исправление последовательностей"""
        print("\n🔄 Проверка последовательностей для столбцов с автоинкрементом...")
        
        # Получаем список всех таблиц с последовательностями
        self.cursor.execute("""
            SELECT 
                c.relname AS sequence_name,
                n.nspname AS schema_name,
                pg_get_serial_sequence(t.relname, a.attname) AS qualified_sequence,
                t.relname AS table_name,
                a.attname AS column_name
            FROM 
                pg_class c
            JOIN 
                pg_namespace n ON n.oid = c.relnamespace
            LEFT JOIN 
                pg_depend d ON d.objid = c.oid AND d.classid = 'pg_class'::regclass AND d.refclassid = 'pg_class'::regclass
            LEFT JOIN 
                pg_class t ON t.oid = d.refobjid AND t.relkind = 'r'
            LEFT JOIN 
                pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid
            WHERE 
                c.relkind = 'S' AND n.nspname = 'public'
            ORDER BY 
                sequence_name;
        """)
        
        sequences = self.cursor.fetchall()
        
        if not sequences:
            print("❓ Не найдено последовательностей для проверки")
            return
        
        fixed_count = 0
        for seq in sequences:
            sequence_name = seq['sequence_name']
            table_name = seq['table_name']
            column_name = seq['column_name']
            qualified_sequence = seq['qualified_sequence']
            
            if not table_name or not column_name:
                continue
                
            # Получаем максимальное значение в столбце
            try:
                self.cursor.execute(f"""
                    SELECT COALESCE(MAX({column_name}), 0) AS max_value
                    FROM {table_name};
                """)
                
                result = self.cursor.fetchone()
                max_value = result['max_value'] if result else 0
                
                # Получаем текущее значение последовательности
                self.cursor.execute(f"""
                    SELECT last_value FROM {sequence_name};
                """)
                
                result = self.cursor.fetchone()
                last_value = result['last_value'] if result else 0
                
                if max_value > last_value:
                    print(f"⚠️ Несоответствие для {table_name}.{column_name}: " 
                          f"max_value={max_value}, last_value={last_value}")
                    
                    # Корректируем последовательность
                    self.cursor.execute(f"""
                        SELECT setval('{qualified_sequence}', {max_value}, true);
                    """)
                    
                    print(f"✅ Последовательность {sequence_name} скорректирована до {max_value}")
                    fixed_count += 1
            except psycopg2.Error as e:
                print(f"❌ Ошибка при проверке последовательности {sequence_name}: {e}")
        
        if fixed_count:
            print(f"✅ Исправлено {fixed_count} последовательностей")
        else:
            print("✅ Все последовательности в порядке!")

    def check_corrupt_tables(self):
        """Проверка на повреждённые таблицы"""
        print("\n🔍 Проверка таблиц на повреждения...")
        
        # Получаем список всех таблиц
        self.cursor.execute("""
            SELECT 
                tablename 
            FROM 
                pg_tables 
            WHERE 
                schemaname = 'public'
            ORDER BY 
                tablename;
        """)
        
        tables = self.cursor.fetchall()
        
        corrupt_tables = []
        for row in tables:
            table_name = row['tablename']
            try:
                # Простая проверка на возможность чтения из таблицы
                self.cursor.execute(f"SELECT 1 FROM {table_name} LIMIT 1;")
                print(f"✓ Таблица {table_name} в порядке")
            except psycopg2.Error as e:
                print(f"❌ Ошибка при доступе к таблице {table_name}: {e}")
                corrupt_tables.append((table_name, str(e)))
        
        if corrupt_tables:
            print(f"\n⚠️ Обнаружено {len(corrupt_tables)} проблемных таблиц:")
            for table, error in corrupt_tables:
                print(f"  - {table}: {error}")
            print("\nРекомендуется выполнить REINDEX для этих таблиц:")
            for table, _ in corrupt_tables:
                print(f"  REINDEX TABLE {table};")
        else:
            print("✅ Все таблицы в порядке!")

    def analyze_performance(self):
        """Анализ производительности базы данных"""
        print("\n📊 Анализ производительности базы данных...")
        
        # Проверка размеров таблиц
        print("\n📏 Размеры таблиц:")
        self.cursor.execute("""
            SELECT
                table_name,
                pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS total_size,
                pg_size_pretty(pg_relation_size(quote_ident(table_name))) AS table_size,
                pg_size_pretty(pg_total_relation_size(quote_ident(table_name)) - 
                               pg_relation_size(quote_ident(table_name))) AS index_size
            FROM
                information_schema.tables
            WHERE
                table_schema = 'public'
            ORDER BY
                pg_total_relation_size(quote_ident(table_name)) DESC
            LIMIT 10;
        """)
        
        tables_size = self.cursor.fetchall()
        
        table_data = []
        for row in tables_size:
            table_data.append([row['table_name'], row['table_size'], 
                              row['index_size'], row['total_size']])
        
        print(tabulate(table_data, headers=["Таблица", "Размер таблицы", "Размер индексов", "Общий размер"]))
        
        # Проверка индексов, которые не используются
        print("\n🔍 Неиспользуемые индексы:")
        self.cursor.execute("""
            SELECT
                s.schemaname,
                s.relname AS table_name,
                s.indexrelname AS index_name,
                pg_size_pretty(pg_relation_size(s.indexrelid)) AS index_size,
                s.idx_scan AS index_scans
            FROM
                pg_stat_user_indexes s
            JOIN
                pg_index i ON s.indexrelid = i.indexrelid
            WHERE
                s.idx_scan = 0 AND
                NOT i.indisprimary AND
                NOT i.indisunique
            ORDER BY
                pg_relation_size(s.indexrelid) DESC;
        """)
        
        unused_indexes = self.cursor.fetchall()
        
        if unused_indexes:
            table_data = []
            for row in unused_indexes:
                table_data.append([row['table_name'], row['index_name'], 
                                  row['index_size'], row['index_scans']])
            
            print(tabulate(table_data, headers=["Таблица", "Индекс", "Размер", "Использований"]))
            
            print("\nРекомендации по неиспользуемым индексам:")
            for row in unused_indexes:
                print(f"-- DROP INDEX IF EXISTS {row['index_name']}; -- размер: {row['index_size']}")
        else:
            print("✅ Не найдено неиспользуемых индексов!")
        
        # Проверка блокировок
        print("\n🔒 Текущие блокировки в базе данных:")
        self.cursor.execute("""
            SELECT 
                blocked_locks.pid AS blocked_pid,
                blocked_activity.usename AS blocked_user,
                blocking_locks.pid AS blocking_pid,
                blocking_activity.usename AS blocking_user,
                blocked_activity.query AS blocked_statement
            FROM 
                pg_catalog.pg_locks blocked_locks
            JOIN 
                pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
            JOIN 
                pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
                AND blocking_locks.DATABASE IS NOT DISTINCT FROM blocked_locks.DATABASE
                AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
                AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
                AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
                AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
                AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
                AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
                AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
                AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
                AND blocking_locks.pid != blocked_locks.pid
            JOIN 
                pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
            WHERE 
                NOT blocked_locks.GRANTED;
        """)
        
        locks = self.cursor.fetchall()
        
        if locks:
            print("⚠️ Обнаружены блокировки:")
            for lock in locks:
                print(f"Процесс {lock['blocked_pid']} заблокирован процессом {lock['blocking_pid']}")
                print(f"Пользователь: {lock['blocked_user']}, блокирующий пользователь: {lock['blocking_user']}")
                print(f"Запрос: {lock['blocked_statement']}")
        else:
            print("✅ Блокировок не обнаружено")

    def run_all_fixes(self):
        """Запуск всех проверок и исправлений"""
        print("🔧 Запуск исправления проблем базы данных PostgreSQL...")
        
        if not self.connect():
            return
        
        try:
            # Запуск всех функций
            self.fix_missing_foreign_key_indexes()
            self.find_tables_without_pk()
            self.vacuum_analyze()
            self.check_sequences()
            self.check_corrupt_tables()
            self.analyze_performance()
            
            print("\n✅ Все операции успешно выполнены!")
            
        except Exception as e:
            print(f"❌ Ошибка при выполнении операций: {e}")
        finally:
            self.close()

def main():
    """Основная функция запуска скрипта"""
    db_fixer = DatabaseFixer(DB_CONFIG)
    db_fixer.run_all_fixes()

if __name__ == "__main__":
    main() 