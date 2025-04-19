from sqlalchemy.orm import Session
import random
import string
from . import models, schemas
from datetime import datetime
from typing import Optional
from fastapi import HTTPException

# Utility functions
def generate_unique_id():
    """Generate a random 20-character uppercase ID"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=20))

# Driver CRUD operations
def get_driver(db: Session, driver_id: int):
    return db.query(models.Driver).filter(models.Driver.id == driver_id).first()

def get_driver_by_unique_id(db: Session, unique_id: str):
    return db.query(models.Driver).filter(models.Driver.unique_id == unique_id).first()

def get_driver_by_license(db: Session, license_number: str):
    return db.query(models.Driver).filter(models.Driver.driver_license_number == license_number).first()

def get_drivers(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Driver).offset(skip).limit(limit).all()

def create_driver(db: Session, driver: schemas.DriverCreate):
    try:
        # Генерируем уникальный ID, если не предоставлен
        unique_id = driver.unique_id.upper() if hasattr(driver, 'unique_id') and driver.unique_id else generate_unique_id()
        
        # Создаем водителя со всеми необходимыми данными
        db_driver = models.Driver(
            full_name=driver.full_name,
            birthdate=driver.birthdate,
            callsign=driver.callsign,
            unique_id=unique_id,
            city=driver.city if hasattr(driver, 'city') and driver.city else "Бишкек",
            driver_license_number=driver.driver_license_number,
            driver_license_issue_date=driver.driver_license_issue_date,
            balance=driver.balance if hasattr(driver, 'balance') and driver.balance is not None else 0.0,
            tariff=driver.tariff,
            taxi_park=driver.taxi_park if hasattr(driver, 'taxi_park') and driver.taxi_park else "Ош Титан Парк"
        )
        db.add(db_driver)
        db.commit()
        db.refresh(db_driver)
        return db_driver
    except Exception as e:
        db.rollback()
        # Добавляем информацию об ошибке
        print(f"Ошибка при создании водителя: {str(e)}")
        # Перебрасываем исключение дальше
        raise

def update_driver(db: Session, driver_id: int, driver_data: schemas.DriverCreate):
    db_driver = get_driver(db, driver_id)
    if db_driver:
        update_data = driver_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_driver, key, value)
        db.commit()
        db.refresh(db_driver)
    return db_driver

def delete_driver(db: Session, driver_id: int):
    db_driver = get_driver(db, driver_id=driver_id)
    if db_driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    # Сохраняем данные, чтобы вернуть после удаления
    driver_data = schemas.Driver.from_orm(db_driver)
    
    # Удаляем связанные с водителем автомобили
    cars = get_driver_cars(db, driver_id=driver_id)
    for car in cars:
        db.delete(car)
    
    # Удаляем водителя
    db.delete(db_driver)
    db.commit()
    
    return driver_data

# Car CRUD operations
def get_car(db: Session, car_id: int):
    return db.query(models.Car).filter(models.Car.id == car_id).first()

def get_car_by_license_plate(db: Session, license_plate: str):
    return db.query(models.Car).filter(models.Car.license_plate == license_plate).first()

def get_car_by_vin(db: Session, vin: str):
    return db.query(models.Car).filter(models.Car.vin == vin).first()

def get_cars(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Car).offset(skip).limit(limit).all()

def get_driver_cars(db: Session, driver_id: int):
    return db.query(models.Car).filter(models.Car.driver_id == driver_id).all()

def create_car(db: Session, car: schemas.CarCreate, driver_id: int):
    try:
        # Создаем словарь с данными машины
        car_data = {}
        
        # Обрабатываем каждое поле из схемы
        if hasattr(car, 'dict'):
            car_dict = car.dict()
            for key, value in car_dict.items():
                car_data[key] = value
        
        # Добавляем ID водителя
        car_data['driver_id'] = driver_id
        
        # Устанавливаем значения по умолчанию, если полей нет
        if 'brand' not in car_data or not car_data['brand']:
            car_data['brand'] = "Не указано"
            
        if 'model' not in car_data or not car_data['model']:
            car_data['model'] = "Не указано"
            
        if 'year' not in car_data:
            car_data['year'] = 2000
            
        if 'transmission' not in car_data or not car_data['transmission']:
            car_data['transmission'] = "Механическая"
            
        if 'tariff' not in car_data or not car_data['tariff']:
            car_data['tariff'] = "Эконом"
            
        if 'license_plate' not in car_data or not car_data['license_plate']:
            car_data['license_plate'] = f"AUTO-{driver_id}"
            
        if 'vin' not in car_data or not car_data['vin']:
            car_data['vin'] = f"VIN-{driver_id}-{car_data['brand']}"
            
        if 'service_type' not in car_data or not car_data['service_type']:
            car_data['service_type'] = "Такси"
        
        # Создаем объект машины
        db_car = models.Car(**car_data)
        db.add(db_car)
        db.commit()
        db.refresh(db_car)
        return db_car
    except Exception as e:
        db.rollback()
        print(f"Ошибка при создании автомобиля: {str(e)}")
        raise

def update_car(db: Session, car_id: int, car_data: schemas.CarCreate):
    db_car = get_car(db, car_id)
    if db_car:
        update_data = car_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_car, key, value)
        db.commit()
        db.refresh(db_car)
    return db_car

def delete_car(db: Session, car_id: int):
    db_car = get_car(db, car_id)
    if db_car:
        db.delete(db_car)
        db.commit()
    return db_car

# Order CRUD operations
def get_order(db: Session, order_id: int):
    return db.query(models.Order).filter(models.Order.id == order_id).first()

def get_orders(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Order).offset(skip).limit(limit).all()

def get_driver_orders(db: Session, driver_id: int):
    return db.query(models.Order).filter(models.Order.driver_id == driver_id).all()

def create_order(db: Session, order: schemas.OrderCreate):
    db_order = models.Order(
        time=order.time,
        origin=order.origin,
        destination=order.destination,
        driver_id=order.driver_id,
        status=order.status,
        price=order.price,
        notes=order.notes,
        payment_method=order.payment_method
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

def update_order(db: Session, order_id: int, order_data: schemas.OrderCreate):
    db_order = get_order(db, order_id)
    if db_order:
        update_data = order_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_order, key, value)
        db.commit()
        db.refresh(db_order)
    return db_order

def delete_order(db: Session, order_id: int):
    db_order = get_order(db, order_id)
    if db_order:
        db.delete(db_order)
        db.commit()
    return db_order

# Message functions
def create_message(db: Session, message: schemas.MessageCreate, sender_id: Optional[int] = None):
    db_message = models.Message(
        sender_id=sender_id,
        recipient_id=message.recipient_id if not message.is_broadcast else None,
        content=message.content,
        is_broadcast=message.is_broadcast
    )
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

def get_messages_for_driver(db: Session, driver_id: int, skip: int = 0, limit: int = 100):
    """Получить все сообщения для конкретного водителя (персональные + общие рассылки)"""
    return db.query(models.Message).filter(
        (models.Message.recipient_id == driver_id) | 
        (models.Message.is_broadcast == True)
    ).order_by(models.Message.created_at.desc()).offset(skip).limit(limit).all()

def get_broadcast_messages(db: Session, skip: int = 0, limit: int = 100):
    """Получить все общие рассылки"""
    return db.query(models.Message).filter(
        models.Message.is_broadcast == True
    ).order_by(models.Message.created_at.desc()).offset(skip).limit(limit).all()

def get_message(db: Session, message_id: int):
    return db.query(models.Message).filter(models.Message.id == message_id).first() 