-- СКРИПТ ДЛЯ ИСПРАВЛЕНИЯ СТРУКТУРЫ БАЗЫ ДАННЫХ WAZIR
-- Разработан на основе database_structure.json

-- 1. УДАЛЕНИЕ ДУБЛИРУЮЩИХСЯ ИНДЕКСОВ
DROP INDEX IF EXISTS ix_autoparks_id;
DROP INDEX IF EXISTS ix_balance_transactions_id;
DROP INDEX IF EXISTS ix_cars_id;
DROP INDEX IF EXISTS ix_driver_cars_id;
DROP INDEX IF EXISTS ix_driver_documents_id;
DROP INDEX IF EXISTS ix_driver_options_id;
DROP INDEX IF EXISTS ix_driver_transactions_id;
DROP INDEX IF EXISTS ix_driver_users_id;
DROP INDEX IF EXISTS ix_driver_verifications_id;
DROP INDEX IF EXISTS ix_drivers_id;
DROP INDEX IF EXISTS ix_messages_id;
DROP INDEX IF EXISTS ix_options_id;
DROP INDEX IF EXISTS ix_orders_id;
DROP INDEX IF EXISTS ix_tariffs_id;
DROP INDEX IF EXISTS ix_users_id;

-- 2. СОЗДАНИЕ НЕДОСТАЮЩИХ ИНДЕКСОВ ДЛЯ ВНЕШНИХ КЛЮЧЕЙ
-- Создаем индексы для всех внешних ключей, которые не имеют своих индексов
CREATE INDEX IF NOT EXISTS idx_balance_transactions_driver_id ON balance_transactions(driver_id);
CREATE INDEX IF NOT EXISTS idx_cars_driver_id ON cars(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_cars_driver_id ON driver_cars(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_documents_driver_id ON driver_documents(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_options_driver_id ON driver_options(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_options_option_id ON driver_options(option_id);
CREATE INDEX IF NOT EXISTS idx_driver_transactions_driver_id ON driver_transactions(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_users_driver_id ON driver_users(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_verifications_driver_id ON driver_verifications(driver_id);
CREATE INDEX IF NOT EXISTS idx_driver_verifications_verified_by ON driver_verifications(verified_by);
CREATE INDEX IF NOT EXISTS idx_drivers_tariff_id ON drivers(tariff_id);
CREATE INDEX IF NOT EXISTS idx_drivers_autopark_id ON drivers(autopark_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages(sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_recipient_id ON messages(recipient_id);
CREATE INDEX IF NOT EXISTS idx_orders_driver_id ON orders(driver_id);

-- 3. УНИФИКАЦИЯ ТИПОВ ДАННЫХ В СВЯЗАННЫХ ТАБЛИЦАХ
-- Изменяем тип данных year в driver_cars с character varying на integer
-- Сначала создаем временную колонку с правильным типом
ALTER TABLE driver_cars ADD COLUMN year_int INTEGER;

-- Затем конвертируем данные (с обработкой NULL и ошибок конвертации)
UPDATE driver_cars SET year_int = 
    CASE 
        WHEN year ~ '^[0-9]+$' THEN year::INTEGER 
        ELSE NULL 
    END;

-- Удаляем старую колонку и переименовываем новую
ALTER TABLE driver_cars DROP COLUMN year;
ALTER TABLE driver_cars RENAME COLUMN year_int TO year;

-- 4. ДОБАВЛЕНИЕ ОГРАНИЧЕНИЙ NOT NULL ДЛЯ ВАЖНЫХ ПОЛЕЙ
-- Сначала исправляем данные в таблице balance_transactions - привязываем транзакции к существующим водителям
-- Исправляем только если есть хотя бы один активный водитель
DO $$
DECLARE
    first_driver_id INTEGER;
BEGIN
    SELECT id INTO first_driver_id FROM drivers WHERE status = 'active' LIMIT 1;
    
    IF first_driver_id IS NOT NULL THEN
        UPDATE balance_transactions SET driver_id = first_driver_id WHERE driver_id IS NULL;
    END IF;
END $$;

-- Добавляем ограничения NOT NULL для важных полей
ALTER TABLE balance_transactions 
    ALTER COLUMN driver_id SET NOT NULL,
    ALTER COLUMN amount SET NOT NULL,
    ALTER COLUMN type SET NOT NULL,
    ALTER COLUMN status SET NOT NULL,
    ALTER COLUMN created_at SET NOT NULL;

ALTER TABLE driver_users
    ALTER COLUMN phone SET NOT NULL,
    ALTER COLUMN first_name SET NOT NULL,
    ALTER COLUMN last_name SET NOT NULL,
    ALTER COLUMN is_verified SET NOT NULL DEFAULT FALSE,
    ALTER COLUMN date_registered SET NOT NULL DEFAULT NOW();

ALTER TABLE drivers
    ALTER COLUMN full_name SET NOT NULL,
    ALTER COLUMN phone SET NOT NULL,
    ALTER COLUMN status SET NOT NULL DEFAULT 'pending',
    ALTER COLUMN balance SET NOT NULL DEFAULT 0,
    ALTER COLUMN created_at SET NOT NULL DEFAULT NOW();

-- 5. ОБЪЕДИНЕНИЕ ТАБЛИЦ CARS И DRIVER_CARS
-- Создаем новую улучшенную таблицу cars_unified, которая объединит данные из обеих таблиц
CREATE TABLE cars_unified (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER NOT NULL REFERENCES drivers(id),
    brand VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    color VARCHAR(50) NOT NULL,
    transmission VARCHAR(50) NOT NULL,
    license_plate VARCHAR(50) UNIQUE NOT NULL,
    vin VARCHAR(50) UNIQUE NOT NULL,
    sts VARCHAR(50),
    has_booster BOOLEAN DEFAULT FALSE,
    has_child_seat BOOLEAN DEFAULT FALSE,
    child_seats INTEGER DEFAULT 0,
    boosters INTEGER DEFAULT 0,
    has_sticker BOOLEAN DEFAULT FALSE,
    has_lightbox BOOLEAN DEFAULT FALSE,
    tariff VARCHAR(50),
    service_type VARCHAR(50),
    is_park_car BOOLEAN DEFAULT FALSE,
    photo_front VARCHAR(255),
    photo_rear VARCHAR(255),
    photo_right VARCHAR(255),
    photo_left VARCHAR(255),
    photo_interior_front VARCHAR(255),
    photo_interior_rear VARCHAR(255),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Создаем индекс для внешнего ключа в новой таблице
CREATE INDEX idx_cars_unified_driver_id ON cars_unified(driver_id);

-- Копируем данные из cars
INSERT INTO cars_unified (
    driver_id, brand, model, year, color, transmission, 
    license_plate, vin, sts, has_booster, has_child_seat,
    tariff, service_type, photo_front, photo_rear, photo_right,
    photo_left, photo_interior_front, photo_interior_rear, has_sticker, has_lightbox
)
SELECT 
    driver_id, brand, model, year, color, transmission, 
    license_plate, vin, sts, has_booster, has_child_seat,
    tariff, service_type, photo_front, photo_rear, photo_right,
    photo_left, photo_interior_front, photo_interior_rear, has_sticker, has_lightbox
FROM cars
ON CONFLICT (license_plate) DO NOTHING;

-- Копируем данные из driver_cars (которые не конфликтуют с данными из cars)
INSERT INTO cars_unified (
    driver_id, brand, model, year, color, transmission, 
    license_plate, vin, sts, boosters, child_seats,
    has_sticker, has_lightbox, is_park_car, 
    photo_front, photo_rear, photo_right, photo_left, 
    photo_interior_front, photo_interior_rear
)
SELECT 
    driver_id, make, model, year, color, transmission, 
    license_plate, vin, sts, boosters, child_seats,
    has_sticker, has_lightbox, is_park_car, 
    front_photo, back_photo, right_photo, left_photo, 
    interior_front_photo, interior_back_photo
FROM driver_cars
WHERE license_plate IS NOT NULL AND vin IS NOT NULL
ON CONFLICT (license_plate) DO NOTHING;

-- Создаем представление для совместимости с существующим кодом
CREATE OR REPLACE VIEW cars_view AS SELECT * FROM cars_unified;
CREATE OR REPLACE VIEW driver_cars_view AS SELECT 
    id, driver_id, brand as make, model, color, year::VARCHAR as year, 
    license_plate, vin, sts, NULL as body_number, transmission, 
    child_seats, boosters, has_sticker, has_lightbox, 
    NULL as registration, is_park_car, NULL as category,
    photo_front as front_photo, photo_rear as back_photo, 
    photo_right as right_photo, photo_left as left_photo,
    photo_interior_front as interior_front_photo, 
    photo_interior_rear as interior_back_photo
FROM cars_unified;

-- Комментарий: Не удаляем сразу исходные таблицы, чтобы не нарушить работу приложения
-- Это можно сделать после тестирования: 
-- DROP TABLE cars CASCADE;
-- DROP TABLE driver_cars CASCADE;

-- 6. ОПТИМИЗАЦИЯ РАБОТЫ БД
-- Анализируем все таблицы для улучшения статистики для планировщика запросов
ANALYZE;

-- Выполняем VACUUM для освобождения места после удаления данных
VACUUM;

-- Создаем функцию для регулярной очистки и анализа таблиц
CREATE OR REPLACE FUNCTION maintenance_db() RETURNS void AS $$
BEGIN
    VACUUM ANALYZE;
END;
$$ LANGUAGE plpgsql;

-- Создаем правило для автоматического выполнения функции каждый день в 3 часа ночи
-- В PostgreSQL это нужно настроить через cron или pg_cron расширение
-- Это только пример того, как это может выглядеть:
-- SELECT cron.schedule('0 3 * * *', 'SELECT maintenance_db()');

-- КОНЕЦ СКРИПТА 