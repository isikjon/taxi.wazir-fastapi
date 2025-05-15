#!/usr/bin/env python
import psycopg2
import psycopg2.extras
import json
from tabulate import tabulate

# Импортируем параметры подключения
from db_params import db_params

def connect_to_db():
    """Подключение к базе данных"""
    try:
        conn = psycopg2.connect(**db_params)
        print(f"✅ Успешное подключение к базе данных {db_params['dbname']} на {db_params['host']}:{db_params['port']}")
        return conn
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return None

def get_tables(conn):
    """Получение списка всех таблиц в базе данных"""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cur.fetchall()]
            print(f"📋 Найдено {len(tables)} таблиц")
            return tables
    except Exception as e:
        print(f"❌ Ошибка при получении списка таблиц: {e}")
        return []

def get_table_size(conn, table_name):
    """Получение размера таблицы"""
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    pg_size_pretty(pg_total_relation_size(%s)) as total_size,
                    pg_size_pretty(pg_relation_size(%s)) as table_size,
                    pg_size_pretty(pg_total_relation_size(%s) - pg_relation_size(%s)) as index_size,
                    (SELECT reltuples FROM pg_class WHERE relname = %s) as row_estimate
            """, (table_name, table_name, table_name, table_name, table_name))
            
            return cur.fetchone()
    except Exception as e:
        print(f"❌ Ошибка при получении размера таблицы {table_name}: {e}")
        return None

def get_table_columns(conn, table_name):
    """Получение информации о столбцах таблицы"""
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT 
                    column_name, 
                    data_type, 
                    character_maximum_length,
                    is_nullable,
                    column_default
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                  AND table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            
            columns = []
            for row in cur.fetchall():
                column_info = dict(row)
                
                # Проверка наличия первичного ключа
                cur.execute("""
                    SELECT 
                        tc.constraint_name,
                        tc.constraint_type
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_schema = 'public'
                      AND tc.table_name = %s
                      AND kcu.column_name = %s
                      AND tc.constraint_type = 'PRIMARY KEY'
                """, (table_name, column_info['column_name']))
                
                is_primary = cur.fetchone() is not None
                column_info['is_primary'] = is_primary
                
                # Проверка наличия внешнего ключа
                cur.execute("""
                    SELECT
                        ccu.table_name AS referenced_table,
                        ccu.column_name AS referenced_column
                    FROM information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.table_schema = 'public'
                      AND tc.table_name = %s
                      AND kcu.column_name = %s
                      AND tc.constraint_type = 'FOREIGN KEY'
                """, (table_name, column_info['column_name']))
                
                fk_info = cur.fetchone()
                if fk_info:
                    column_info['foreign_key'] = {
                        'referenced_table': fk_info['referenced_table'],
                        'referenced_column': fk_info['referenced_column']
                    }
                
                columns.append(column_info)
            
            return columns
    except Exception as e:
        print(f"❌ Ошибка при получении столбцов таблицы {table_name}: {e}")
        return []

def get_indexes(conn, table_name):
    """Получение информации об индексах таблицы"""
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    i.relname AS index_name,
                    array_to_string(array_agg(a.attname), ', ') AS column_names,
                    ix.indisunique AS is_unique,
                    ix.indisprimary AS is_primary
                FROM
                    pg_class t,
                    pg_class i,
                    pg_index ix,
                    pg_attribute a
                WHERE
                    t.oid = ix.indrelid
                    AND i.oid = ix.indexrelid
                    AND a.attrelid = t.oid
                    AND a.attnum = ANY(ix.indkey)
                    AND t.relkind = 'r'
                    AND t.relname = %s
                GROUP BY
                    i.relname,
                    ix.indisunique,
                    ix.indisprimary
                ORDER BY
                    i.relname;
            """, (table_name,))
            
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Ошибка при получении индексов таблицы {table_name}: {e}")
        return []

def get_table_constraints(conn, table_name):
    """Получение ограничений таблицы"""
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT
                    tc.constraint_name,
                    tc.constraint_type,
                    kcu.column_name,
                    ccu.table_name AS referenced_table,
                    ccu.column_name AS referenced_column
                FROM
                    information_schema.table_constraints AS tc
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                    LEFT JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                WHERE
                    tc.table_schema = 'public'
                    AND tc.table_name = %s
                ORDER BY
                    tc.constraint_name,
                    kcu.column_name
            """, (table_name,))
            
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Ошибка при получении ограничений таблицы {table_name}: {e}")
        return []

def get_sample_data(conn, table_name, limit=5):
    """Получение образца данных из таблицы"""
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT * FROM {table_name} LIMIT %s", (limit,))
            return [dict(row) for row in cur.fetchall()]
    except Exception as e:
        print(f"❌ Ошибка при получении данных из таблицы {table_name}: {e}")
        return []

def analyze_database():
    """Основная функция анализа базы данных"""
    conn = connect_to_db()
    if not conn:
        print("Не удалось подключиться к базе данных. Завершение работы.")
        return
    
    try:
        tables = get_tables(conn)
        
        database_structure = {
            "database_name": db_params['dbname'],
            "tables": {}
        }
        
        print("\n🔍 Анализ структуры базы данных:\n")
        
        for table_name in tables:
            print(f"\n📊 Анализ таблицы: {table_name}")
            
            # Размер таблицы
            size_info = get_table_size(conn, table_name)
            if size_info:
                total_size, table_size, index_size, row_estimate = size_info
                print(f"Общий размер: {total_size}, Размер таблицы: {table_size}, Размер индексов: {index_size}, Примерное количество строк: {int(row_estimate) if row_estimate else 0}")
            
            columns = get_table_columns(conn, table_name)
            indexes = get_indexes(conn, table_name)
            constraints = get_table_constraints(conn, table_name)
            sample_data = get_sample_data(conn, table_name)
            
            # Вывод информации о столбцах в виде таблицы
            columns_data = []
            for col in columns:
                data_type = col['data_type']
                if col['character_maximum_length']:
                    data_type += f"({col['character_maximum_length']})"
                
                fk_info = ''
                if 'foreign_key' in col:
                    fk_info = f" -> {col['foreign_key']['referenced_table']}.{col['foreign_key']['referenced_column']}"
                
                pk_info = '🔑 PK' if col['is_primary'] else ''
                nullable = 'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'
                
                columns_data.append([
                    col['column_name'],
                    data_type,
                    nullable,
                    col['column_default'] or '',
                    pk_info,
                    fk_info
                ])
            
            print("\nСтолбцы:")
            print(tabulate(
                columns_data, 
                headers=["Имя", "Тип", "Null", "По умолчанию", "PK", "FK"]
            ))
            
            # Вывод информации об индексах
            if indexes:
                print("\nИндексы:")
                indexes_data = []
                for idx in indexes:
                    indexes_data.append([
                        idx['index_name'],
                        idx['column_names'],
                        '✓' if idx['is_unique'] else '',
                        '✓' if idx['is_primary'] else ''
                    ])
                
                print(tabulate(
                    indexes_data,
                    headers=["Имя индекса", "Столбцы", "Уникальный", "Первичный ключ"]
                ))
            
            # Вывод информации об ограничениях
            if constraints:
                print("\nОграничения:")
                constraints_data = []
                for constraint in constraints:
                    ref_info = ''
                    if constraint['constraint_type'] == 'FOREIGN KEY':
                        ref_info = f"{constraint['referenced_table']}.{constraint['referenced_column']}"
                    
                    constraints_data.append([
                        constraint['constraint_name'],
                        constraint['constraint_type'],
                        constraint['column_name'],
                        ref_info
                    ])
                
                print(tabulate(
                    constraints_data,
                    headers=["Имя ограничения", "Тип", "Столбец", "Ссылка"]
                ))
            
            # Вывод образца данных
            if sample_data:
                print("\nОбразец данных (максимум 5 строк):")
                print(tabulate(sample_data, headers="keys"))
            
            # Сохранение информации о таблице
            database_structure["tables"][table_name] = {
                "columns": columns,
                "indexes": indexes,
                "constraints": constraints,
                "sample_data": sample_data,
                "size_info": size_info
            }
            
            print(f"✅ Таблица {table_name} успешно проанализирована")
        
        # Анализ всей базы данных
        print("\n🔍 Анализ и рекомендации для всей базы данных:")
        
        # Проверка на таблицы без первичных ключей
        tables_without_pk = []
        for table_name, table_info in database_structure["tables"].items():
            has_pk = False
            for col in table_info["columns"]:
                if col["is_primary"]:
                    has_pk = True
                    break
            
            if not has_pk:
                tables_without_pk.append(table_name)
        
        if tables_without_pk:
            print(f"⚠️ Таблицы без первичного ключа: {', '.join(tables_without_pk)}")
            print("   Рекомендуется добавить первичный ключ для повышения производительности и целостности данных")
        
        # Проверка на индексы для внешних ключей
        fk_without_indexes = []
        for table_name, table_info in database_structure["tables"].items():
            for col in table_info["columns"]:
                if 'foreign_key' in col:
                    # Проверяем, есть ли индекс для этого FK
                    has_index = False
                    for idx in table_info["indexes"]:
                        if col["column_name"] in idx["column_names"]:
                            has_index = True
                            break
                    
                    if not has_index:
                        fk_without_indexes.append(f"{table_name}.{col['column_name']}")
        
        if fk_without_indexes:
            print(f"\n⚠️ Внешние ключи без индексов: {', '.join(fk_without_indexes)}")
            print("   Рекомендуется добавить индексы для внешних ключей для повышения производительности запросов JOIN")
            for fk in fk_without_indexes:
                table, column = fk.split('.')
                print(f"   CREATE INDEX idx_{table}_{column} ON {table}({column});")
        
        # Проверка на крупные таблицы без достаточного количества индексов
        large_tables_without_indexes = []
        for table_name, table_info in database_structure["tables"].items():
            if table_info.get("size_info") and float(table_info["size_info"][3] or 0) > 10000:  # если больше 10к строк
                if len(table_info["indexes"]) < 2:  # если меньше 2 индексов
                    large_tables_without_indexes.append(table_name)
        
        if large_tables_without_indexes:
            print(f"\n⚠️ Крупные таблицы с недостаточным количеством индексов: {', '.join(large_tables_without_indexes)}")
            print("   Рекомендуется проанализировать запросы к этим таблицам и добавить индексы для часто используемых столбцов")
        
        # Сохранение результата анализа в JSON файл
        with open('database_structure.json', 'w', encoding='utf-8') as f:
            json.dump(database_structure, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n📄 Результаты анализа сохранены в файл database_structure.json")
        
    except Exception as e:
        print(f"❌ Ошибка при анализе базы данных: {e}")
    finally:
        conn.close()
        print("\n👋 Анализ базы данных завершен")

if __name__ == "__main__":
    analyze_database() 