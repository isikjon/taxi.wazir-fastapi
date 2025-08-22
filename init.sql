CREATE DATABASE wazir_db;
\c wazir_db;

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS drivers (
    id SERIAL PRIMARY KEY,
    unique_id VARCHAR(20) UNIQUE NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    birth_date DATE NOT NULL,
    callsign VARCHAR(50) NOT NULL,
    city VARCHAR(100) NOT NULL,
    driver_license_number VARCHAR(50) UNIQUE NOT NULL,
    driver_license_issue_date DATE,
    balance DECIMAL(10,2) DEFAULT 0.0,
    tariff VARCHAR(50) NOT NULL,
    taxi_park VARCHAR(100),
    phone VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    activity INTEGER DEFAULT 0,
    rating VARCHAR(10) DEFAULT '5.000',
    is_mobile_registered BOOLEAN DEFAULT FALSE,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    address VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS cars (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER REFERENCES drivers(id) ON DELETE CASCADE,
    brand VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    year INTEGER NOT NULL,
    transmission VARCHAR(50) NOT NULL,
    has_booster BOOLEAN DEFAULT FALSE,
    has_child_seat BOOLEAN DEFAULT FALSE,
    has_sticker BOOLEAN DEFAULT FALSE,
    has_lightbox BOOLEAN DEFAULT FALSE,
    tariff VARCHAR(50) NOT NULL,
    license_plate VARCHAR(50) UNIQUE NOT NULL,
    vin VARCHAR(50) UNIQUE NOT NULL,
    service_type VARCHAR(50) NOT NULL,
    color VARCHAR(50),
    sts VARCHAR(50),
    photo_front VARCHAR(255),
    photo_rear VARCHAR(255),
    photo_right VARCHAR(255),
    photo_left VARCHAR(255),
    photo_interior_front VARCHAR(255),
    photo_interior_rear VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(20) UNIQUE NOT NULL,
    driver_id INTEGER REFERENCES drivers(id) ON DELETE SET NULL,
    pickup_time TIMESTAMP,
    pickup_address TEXT,
    destination_address TEXT,
    tariff VARCHAR(50),
    status VARCHAR(50) DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER,
    receiver_id INTEGER,
    message_text TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_read BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS balance_transactions (
    id SERIAL PRIMARY KEY,
    driver_id INTEGER REFERENCES drivers(id) ON DELETE CASCADE,
    amount DECIMAL(10,2) NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,
    description TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_drivers_unique_id ON drivers(unique_id);
CREATE INDEX idx_drivers_phone ON drivers(phone);
CREATE INDEX idx_cars_driver_id ON cars(driver_id);
CREATE INDEX idx_cars_license_plate ON cars(license_plate);
CREATE INDEX idx_orders_driver_id ON orders(driver_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_messages_sender_receiver ON messages(sender_id, receiver_id);
