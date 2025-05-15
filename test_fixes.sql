-- ЗАПРОСЫ ДЛЯ ПРОВЕРКИ ЭФФЕКТИВНОСТИ ИСПРАВЛЕНИЙ
-- Запустить после выполнения fix_database.sql

-- 1. Проверка удаления дублирующихся индексов
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename IN (
    'alembic_version', 'autoparks', 'balance_transactions', 'cars', 'driver_cars',
    'driver_documents', 'driver_options', 'driver_transactions', 'driver_users',
    'driver_verifications', 'drivers', 'messages', 'options', 'orders', 'tariffs', 'users'
)
ORDER BY tablename, indexname;

-- 2. Проверка созданных индексов для внешних ключей
SELECT 
    tc.table_name, kcu.column_name, 
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name,
    (SELECT count(*) FROM pg_indexes 
     WHERE tablename = tc.table_name 
     AND indexdef LIKE '%' || kcu.column_name || '%') AS has_index
FROM 
    information_schema.table_constraints AS tc 
    JOIN information_schema.key_column_usage AS kcu
      ON tc.constraint_name = kcu.constraint_name
      AND tc.table_schema = kcu.table_schema
    JOIN information_schema.constraint_column_usage AS ccu
      ON ccu.constraint_name = tc.constraint_name
      AND ccu.table_schema = tc.table_schema
WHERE tc.constraint_type = 'FOREIGN KEY'
ORDER BY tc.table_name, kcu.column_name;

-- 3. Проверка унификации типов данных в driver_cars
SELECT column_name, data_type, character_maximum_length, is_nullable
FROM information_schema.columns
WHERE table_name = 'driver_cars' AND column_name = 'year';

-- 4. Проверка ограничений NOT NULL
SELECT 
    table_name, column_name, is_nullable, column_default
FROM 
    information_schema.columns
WHERE 
    table_name IN ('balance_transactions', 'driver_users', 'drivers') AND
    column_name IN ('driver_id', 'amount', 'type', 'status', 'created_at', 
                    'phone', 'first_name', 'last_name', 'is_verified', 
                    'date_registered', 'full_name', 'balance')
ORDER BY table_name, column_name;

-- 5. Проверка объединенной таблицы cars_unified
SELECT 
    table_name, column_name, data_type, character_maximum_length, is_nullable
FROM 
    information_schema.columns
WHERE 
    table_name = 'cars_unified'
ORDER BY column_name;

-- 6. Подсчет данных в новой объединенной таблице
SELECT count(*) FROM cars_unified;

-- 7. Проверка представлений для обратной совместимости
SELECT table_name, view_definition
FROM information_schema.views
WHERE table_name IN ('cars_view', 'driver_cars_view');

-- 8. Общая информация по индексам после оптимизации
SELECT
    pg_size_pretty(pg_total_relation_size(indexrelid)) AS index_size,
    idx.relname AS index_name,
    idx.reltuples AS index_entries,
    tab.relname AS table_name,
    am.amname AS index_type
FROM
    pg_index i
    JOIN pg_class idx ON idx.oid = i.indexrelid
    JOIN pg_class tab ON tab.oid = i.indrelid
    JOIN pg_am am ON am.oid = idx.relam
WHERE
    tab.relname IN (
        'alembic_version', 'autoparks', 'balance_transactions', 'cars_unified',
        'driver_documents', 'driver_options', 'driver_transactions', 'driver_users',
        'driver_verifications', 'drivers', 'messages', 'options', 'orders', 'tariffs', 'users'
    )
ORDER BY pg_total_relation_size(indexrelid) DESC;

-- 9. Проверка наличия функции обслуживания БД
SELECT 
    proname, prosrc 
FROM 
    pg_proc 
WHERE 
    proname = 'maintenance_db';

-- 10. Запрос для тестирования производительности JOINs
EXPLAIN ANALYZE
SELECT d.full_name, d.phone, d.status, c.brand, c.model, c.license_plate
FROM drivers d
JOIN cars_unified c ON d.id = c.driver_id
WHERE d.status = 'active';

-- Сравнить с тем же запросом до оптимизации (сохранен в cars_backup)
EXPLAIN ANALYZE
SELECT d.full_name, d.phone, d.status, c.brand, c.model, c.license_plate
FROM drivers_backup d
JOIN cars_backup c ON d.id = c.driver_id
WHERE d.status = 'active'; 