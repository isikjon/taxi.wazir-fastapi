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

# Order CRUD operations
def create_order(db: Session, order: schemas.OrderCreate):
    """Создает новый заказ в БД"""
    try:
        # Создаем объект заказа с ВСЕМИ полями включая координаты
        db_order = models.Order(
            order_number=order.order_number,
            time=order.time,
            origin=order.origin,
            destination=order.destination,
            origin_lat=order.origin_lat,        # ВАЖНО! 
            origin_lng=order.origin_lng,        # ВАЖНО!
            destination_lat=order.destination_lat,  # ВАЖНО!
            destination_lng=order.destination_lng,  # ВАЖНО!
            driver_id=order.driver_id,
            status=order.status or "Ожидает водителя",
            price=order.price,
            tariff=order.tariff,
            notes=order.notes,
            payment_method=order.payment_method,
            created_at=datetime.now()
        )
        
        # Сохраняем в БД
        db.add(db_order)
        db.commit()
        db.refresh(db_order)
        
        print(f"✅ ЗАКАЗ СОЗДАН: ID={db_order.id}, origin_lat={db_order.origin_lat}, origin_lng={db_order.origin_lng}")
        print(f"✅ КООРДИНАТЫ: destination_lat={db_order.destination_lat}, destination_lng={db_order.destination_lng}")
        
        return db_order
        
    except Exception as e:
        db.rollback()
        print(f"❌ ОШИБКА создания заказа: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания заказа: {str(e)}")

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
        
        # Обработка значения рейтинга, заменяем запятую на точку
        rating_value = 5.0  # Значение по умолчанию
        
        # Создаем водителя со всеми необходимыми данными
        db_driver = models.Driver(
            full_name=driver.full_name,
            birth_date=driver.birth_date,
            callsign=driver.callsign,
            unique_id=unique_id,
            city=driver.city if hasattr(driver, 'city') and driver.city else "Бишкек",
            driver_license_number=driver.driver_license_number,
            driver_license_issue_date=driver.driver_license_issue_date,
            balance=driver.balance if hasattr(driver, 'balance') and driver.balance is not None else 0.0,
            tariff=driver.tariff,
            taxi_park=driver.taxi_park if hasattr(driver, 'taxi_park') and driver.taxi_park else "Ош Титан Парк",
            phone=driver.phone if hasattr(driver, 'phone') and driver.phone else None,
            status="pending",
            activity=0,
            rating="5.000",  # Используем точку вместо запятой
            is_mobile_registered=driver.is_mobile_registered if hasattr(driver, 'is_mobile_registered') else False,
            registration_date=driver.registration_date if hasattr(driver, 'registration_date') else datetime.now()
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

def update_driver(db: Session, driver_id: int, driver_data: dict):
    db_driver = get_driver(db, driver_id=driver_id)
    if db_driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    # Обновляем поля водителя
    for key, value in driver_data.items():
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
    
    # Очищаем связи в таблице orders
    try:
        db.query(models.Order).filter(models.Order.driver_id == driver_id).update(
            {models.Order.driver_id: None}
        )
    except Exception as e:
        print(f"Ошибка при обновлении orders: {str(e)}")
    
    # Очищаем связи в таблице balance_transactions
    try:
        db.query(models.BalanceTransaction).filter(models.BalanceTransaction.driver_id == driver_id).update(
            {models.BalanceTransaction.driver_id: None}
        )
    except Exception as e:
        print(f"Ошибка при обновлении balance_transactions: {str(e)}")
    
    # Удаляем записи в таблице driver_documents
    try:
        documents = db.query(models.DriverDocuments).filter(models.DriverDocuments.driver_id == driver_id).all()
        for doc in documents:
            db.delete(doc)
    except Exception as e:
        print(f"Ошибка при удалении driver_documents: {str(e)}")
        
    # Удаляем записи в таблице driver_verifications
    try:
        verifications = db.query(models.DriverVerification).filter(models.DriverVerification.driver_id == driver_id).all()
        for verification in verifications:
            db.delete(verification)
    except Exception as e:
        print(f"Ошибка при удалении driver_verifications: {str(e)}")
    
    # Очищаем связи в таблице driver_users
    try:
        db.query(models.DriverUser).filter(models.DriverUser.driver_id == driver_id).update(
            {models.DriverUser.driver_id: None}
        )
    except Exception as e:
        print(f"Ошибка при обновлении driver_users: {str(e)}")
    
    # Очищаем связи в таблице messages (отправитель)
    try:
        db.query(models.Message).filter(models.Message.sender_id == driver_id).update(
            {models.Message.sender_id: None}
        )
    except Exception as e:
        print(f"Ошибка при обновлении messages (sender): {str(e)}")
    
    # Очищаем связи в таблице messages (получатель)
    try:
        db.query(models.Message).filter(models.Message.recipient_id == driver_id).update(
            {models.Message.recipient_id: None}
        )
    except Exception as e:
        print(f"Ошибка при обновлении messages (recipient): {str(e)}")
    
    # Удаляем связанные автомобили
    try:
        cars = get_driver_cars(db, driver_id=driver_id)
        for car in cars:
            db.delete(car)
    except Exception as e:
        print(f"Ошибка при удалении cars: {str(e)}")
    
    # Удаляем связанные записи в таблице driver_cars
    try:
        driver_cars = db.query(models.DriverCar).filter(models.DriverCar.driver_id == driver_id).all()
        for car in driver_cars:
            db.delete(car)
    except Exception as e:
        print(f"Ошибка при удалении driver_cars: {str(e)}")
    
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
            
        if 'color' not in car_data or not car_data['color']:
            car_data['color'] = "Не указано"
            
        if 'sts' not in car_data or not car_data['sts']:
            car_data['sts'] = "Не указано"
            
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

def update_car(db: Session, car_id: int, car_data: dict):
    db_car = db.query(models.Car).filter(models.Car.id == car_id).first()
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    
    # Обновляем поля автомобиля
    for key, value in car_data.items():
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
        order_number=order.order_number,
        time=order.time,
        origin=order.origin,
        destination=order.destination,
        driver_id=order.driver_id,
        status=order.status,
        price=order.price,
        tariff=order.tariff,
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

def create_driver_user(db: Session, user):
    """Создает нового пользователя-водителя"""
    print(f"CRUD: Создание пользователя с данными: {user}")
    
    # Проверяем, является ли user словарем или объектом Pydantic
    if hasattr(user, 'model_dump'):
        user_data = user.model_dump()
    elif hasattr(user, 'dict'):
        user_data = user.dict()
    else:
        user_data = user  # Предполагаем, что это уже словарь
    
    print(f"CRUD: Данные для создания: {user_data}")
        
    db_user = models.DriverUser(**user_data)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    print(f"CRUD: Пользователь создан: id={db_user.id}, phone={db_user.phone}")
    return db_user

def get_driver_user_by_phone(db: Session, phone: str):
    """Получает пользователя-водителя по номеру телефона"""
    print(f"CRUD: Поиск пользователя по телефону: {phone}")
    
    user = db.query(models.DriverUser).filter(models.DriverUser.phone == phone).first()
    
    if user:
        print(f"CRUD: Найден пользователь: id={user.id}, phone={user.phone}, first_name='{user.first_name}', last_name='{user.last_name}'")
    else:
        print(f"CRUD: Пользователь с телефоном {phone} не найден")
    
    return user

def get_driver_user(db: Session, user_id: int):
    """Получает пользователя-водителя по ID"""
    print(f"CRUD: Поиск пользователя по ID: {user_id}")
    
    user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
    
    if user:
        print(f"CRUD: Найден пользователь: id={user.id}, phone={user.phone}, first_name='{user.first_name}', last_name='{user.last_name}'")
    else:
        print(f"CRUD: Пользователь с ID {user_id} не найден")
    
    return user

def update_driver_user(db: Session, user_id: int, user_data: schemas.DriverUserUpdate):
    """Обновляет данные пользователя-водителя"""
    print(f"CRUD: Обновление пользователя {user_id} с данными: {user_data}")
    
    db_user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
    if not db_user:
        print(f"CRUD: Пользователь {user_id} не найден")
        return None
    
    print(f"CRUD: Найден пользователь: id={db_user.id}, phone={db_user.phone}")
    
    # Получаем данные для обновления
    if hasattr(user_data, 'model_dump'):
        update_data = user_data.model_dump(exclude_unset=False)  # Убираем exclude_unset=True
        print(f"CRUD: Используем model_dump, exclude_unset=False")
    else:
        update_data = user_data.dict(exclude_unset=False)  # Убираем exclude_unset=True
        print(f"CRUD: Используем dict, exclude_unset=False")
    
    print(f"CRUD: Данные для обновления: {update_data}")
    print(f"CRUD: Тип update_data: {type(update_data)}")
    
    # Проверяем, что данные не пустые
    if not update_data:
        print(f"CRUD: ВНИМАНИЕ! update_data пустой!")
        return None
    
    for key, value in update_data.items():
        print(f"CRUD: Устанавливаем {key} = '{value}' (тип: {type(value)})")
        # Убеждаемся, что строки не пустые
        if isinstance(value, str) and value.strip() == '':
            value = None
            print(f"CRUD: Пустая строка заменена на None для {key}")
        setattr(db_user, key, value)
    
    print(f"CRUD: Перед commit: first_name='{db_user.first_name}', last_name='{db_user.last_name}'")
    
    try:
        db.commit()
        print(f"CRUD: Commit успешен")
    except Exception as e:
        print(f"CRUD: Ошибка при commit: {e}")
        db.rollback()
        raise
    
    db.refresh(db_user)
    
    print(f"CRUD: После refresh: first_name='{db_user.first_name}', last_name='{db_user.last_name}'")
    print(f"CRUD: Пользователь обновлен: id={db_user.id}, first_name='{db_user.first_name}', last_name='{db_user.last_name}'")
    return db_user

def update_last_login(db: Session, user_id: int):
    """Обновляет время последнего входа"""
    db_user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
    if db_user:
        db_user.last_login = datetime.now()
        db.commit()
        print(f"CRUD: Обновлено время последнего входа для пользователя {user_id}")
    return db_user

# Функция для получения водителя по номеру телефона
def get_driver_by_phone(db: Session, phone: str):
    return db.query(models.Driver).filter(models.Driver.phone == phone).first()

# Функция для получения автомобиля по ID водителя
def get_car_by_driver_id(db: Session, driver_id: int):
    return db.query(models.Car).filter(models.Car.driver_id == driver_id).first()

# Функция для получения водителя по ID пользователя
def get_driver_by_user_id(db: Session, user_id: int):
    # Сначала получаем пользователя
    user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
    if not user:
        return None
        
    # Если у пользователя есть связанный водитель, возвращаем его
    return db.query(models.Driver).filter(models.Driver.id == user.driver_id).first() 