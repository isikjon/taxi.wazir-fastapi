-- СКРИПТ ДЛЯ СОЗДАНИЯ РЕЗЕРВНОЙ КОПИИ СХЕМЫ БАЗЫ ДАННЫХ
-- Выполнить перед запуском fix_database.sql

-- Создание резервной копии таблиц и их содержимого
-- Запустите эту команду из командной строки:
-- pg_dump -h localhost -U your_user -d wazir -f wazir_backup_full.sql

-- Для создания только копии структуры без данных:
-- pg_dump -h localhost -U your_user -d wazir --schema-only -f wazir_backup_schema.sql

-- Создаем резервные таблицы для таблиц, которые будут модифицированы
CREATE TABLE IF NOT EXISTS balance_transactions_backup AS TABLE balance_transactions;
CREATE TABLE IF NOT EXISTS driver_cars_backup AS TABLE driver_cars;
CREATE TABLE IF NOT EXISTS cars_backup AS TABLE cars;
CREATE TABLE IF NOT EXISTS driver_users_backup AS TABLE driver_users;
CREATE TABLE IF NOT EXISTS drivers_backup AS TABLE drivers;

-- Создаем резервные копии индексов
CREATE TABLE IF NOT EXISTS pg_indexes_backup AS 
SELECT * FROM pg_indexes WHERE tablename IN (
    'alembic_version', 'autoparks', 'balance_transactions', 'cars', 'driver_cars',
    'driver_documents', 'driver_options', 'driver_transactions', 'driver_users',
    'driver_verifications', 'drivers', 'messages', 'options', 'orders', 'tariffs', 'users'
);

-- Сохраняем информацию о внешних ключах
CREATE TABLE IF NOT EXISTS pg_constraints_backup AS
SELECT * FROM pg_constraint c 
JOIN pg_namespace n ON n.oid = c.connamespace
JOIN pg_class cl ON cl.oid = c.conrelid
WHERE n.nspname = 'public' AND c.contype = 'f';

-- Создаем функцию для возврата к предыдущему состоянию в случае ошибок
CREATE OR REPLACE FUNCTION rollback_database_changes() RETURNS void AS $$
BEGIN
    -- Восстанавливаем данные из резервных таблиц
    TRUNCATE TABLE balance_transactions;
    INSERT INTO balance_transactions SELECT * FROM balance_transactions_backup;
    
    TRUNCATE TABLE driver_cars;
    INSERT INTO driver_cars SELECT * FROM driver_cars_backup;
    
    TRUNCATE TABLE cars;
    INSERT INTO cars SELECT * FROM cars_backup;
    
    TRUNCATE TABLE driver_users;
    INSERT INTO driver_users SELECT * FROM driver_users_backup;
    
    TRUNCATE TABLE drivers;
    INSERT INTO drivers SELECT * FROM drivers_backup;
    
    -- Восстанавливаем удаленные индексы (здесь потребуется ручная работа)
    -- По данным из pg_indexes_backup
    
    -- Удаляем резервные таблицы
    DROP TABLE IF EXISTS balance_transactions_backup;
    DROP TABLE IF EXISTS driver_cars_backup;
    DROP TABLE IF EXISTS cars_backup;
    DROP TABLE IF EXISTS driver_users_backup;
    DROP TABLE IF EXISTS drivers_backup;
    DROP TABLE IF EXISTS pg_indexes_backup;
    DROP TABLE IF EXISTS pg_constraints_backup;

    RAISE NOTICE 'База данных восстановлена из резервных копий';
END;
$$ LANGUAGE plpgsql;

-- Примечание: Чтобы выполнить откат, запустите:
-- SELECT rollback_database_changes(); 