from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Date, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .database import Base

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    unique_id = Column(String(20), unique=True, index=True)
    full_name = Column(String(255), nullable=False)
    birth_date = Column(Date, nullable=False)
    callsign = Column(String(50), nullable=False)
    city = Column(String(100), nullable=False)
    driver_license_number = Column(String(50), unique=True, nullable=False)
    driver_license_issue_date = Column(Date, nullable=True)
    balance = Column(Float, default=0.0)
    tariff = Column(String(50), nullable=False)  # Бюджетный, Стандартный, Бизнес, Люкс
    taxi_park = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)  # Номер телефона водителя
    status = Column(String(20), default="pending")  # accepted, rejected, pending
    
    # Новые поля для активности и рейтинга
    activity = Column(Integer, default=0)  # Количество заказов/активность водителя
    rating = Column(String, default="5.000")  # Рейтинг водителя
    
    # Поле для отметки о том, что водитель зарегистрирован через мобильное приложение
    is_mobile_registered = Column(Boolean, default=False)
    
    # Дата регистрации водителя
    registration_date = Column(DateTime, default=datetime.now)
    
    # Адрес водителя
    address = Column(String(255), nullable=True)
    
    cars = relationship("Car", back_populates="driver")
    
    orders = relationship("Order", back_populates="driver")

    transactions = relationship("BalanceTransaction", back_populates="driver")
    
    @property
    def car(self):
        """Возвращает первый автомобиль водителя (для обратной совместимости)"""
        return self.cars[0] if self.cars else None
        
    @car.setter
    def car(self, value):
        """Сеттер для атрибута car (нужен для ручного присваивания)"""
        if not hasattr(self, '_car'):
            self._car = value

    @property
    def is_busy(self):
        """Возвращает занятость водителя (для обратной совместимости)"""
        # Проверяем наличие активных заказов
        return any(order.status == "Занят" for order in self.orders) if hasattr(self, 'orders') and self.orders else False


class Car(Base):
    __tablename__ = "cars"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    brand = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    year = Column(Integer, nullable=False)
    transmission = Column(String(50), nullable=False)  # механика, автомат
    has_booster = Column(Boolean, default=False)
    has_child_seat = Column(Boolean, default=False)
    has_sticker = Column(Boolean, default=False)
    has_lightbox = Column(Boolean, default=False)
    tariff = Column(String(50), nullable=False)  # Бюджетный, Стандартный, Бизнес, Люкс
    license_plate = Column(String(50), unique=True, nullable=False)
    vin = Column(String(50), unique=True, nullable=False)
    service_type = Column(String(50), nullable=False)  # Грузоперевозка, Такси
    color = Column(String(50), nullable=True)  # Цвет автомобиля
    sts = Column(String(50), nullable=True)  # Свидетельство о регистрации ТС
    
    # Пути к фотографиям
    photo_front = Column(String(255), nullable=True)
    photo_rear = Column(String(255), nullable=True)
    photo_right = Column(String(255), nullable=True)
    photo_left = Column(String(255), nullable=True)
    photo_interior_front = Column(String(255), nullable=True)
    photo_interior_rear = Column(String(255), nullable=True)
    
    # Связь с водителем
    driver = relationship("Driver", back_populates="cars")


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(20), nullable=False, unique=True)  # Номер заказа
    time = Column(String(8), nullable=False)  # чч:мм:сс
    origin = Column(Text, nullable=False)  # Откуда
    destination = Column(Text, nullable=False)  # Куда
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    created_at = Column(DateTime, server_default=func.now())
    status = Column(String(50), default="Выполняется")  # Выполняется, Завершен, Отменен
    price = Column(Float, nullable=True)  # Стоимость поездки
    tariff = Column(String(50), nullable=True)  # Тариф (Эконом, Комфорт, и т.д.)
    notes = Column(Text, nullable=True)  # Примечание от диспетчера
    payment_method = Column(String(50), nullable=True)  # Способ оплаты
    
    # Связь с водителем
    driver = relationship("Driver", back_populates="orders")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)  # NULL если отправитель - диспетчер
    recipient_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)  # NULL для общей рассылки
    content = Column(Text, nullable=False)
    is_broadcast = Column(Boolean, default=False)  # True для общей рассылки
    created_at = Column(DateTime, server_default=func.now())
    
    # Связь с отправителем (если это водитель)
    sender = relationship("Driver", foreign_keys=[sender_id], backref="sent_messages")
    
    # Связь с получателем (если это конкретный водитель)
    recipient = relationship("Driver", foreign_keys=[recipient_id], backref="received_messages")


class BalanceTransaction(Base):
    __tablename__ = "balance_transactions"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    amount = Column(Float)
    type = Column(String)  # deposit, withdrawal
    status = Column(String)  # completed, pending, cancelled
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    driver = relationship("Driver", back_populates="transactions")


class DriverUser(Base):
    __tablename__ = "driver_users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(50), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    is_verified = Column(Boolean, default=False)
    date_registered = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, nullable=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    
    # Связь с водителем
    driver = relationship("Driver", backref="user_account")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    has_driver: bool = False
    driver_id: Optional[int] = None


class DriverCar(Base):
    __tablename__ = "driver_cars"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    make = Column(String(100), nullable=True)
    model = Column(String(100), nullable=True)
    color = Column(String(50), nullable=True)
    year = Column(String(10), nullable=True)
    license_plate = Column(String(50), nullable=True)
    vin = Column(String(50), nullable=True)
    sts = Column(String(50), nullable=True)
    body_number = Column(String(100), nullable=True)
    transmission = Column(String(50), nullable=True)
    child_seats = Column(Integer, default=0)
    boosters = Column(Integer, default=0)
    has_sticker = Column(Boolean, default=False)
    has_lightbox = Column(Boolean, default=False)
    registration = Column(String(50), nullable=True)
    is_park_car = Column(Boolean, default=False)
    category = Column(String(50), nullable=True)
    front_photo = Column(String(255), nullable=True)
    back_photo = Column(String(255), nullable=True)
    right_photo = Column(String(255), nullable=True)
    left_photo = Column(String(255), nullable=True)
    interior_front_photo = Column(String(255), nullable=True)
    interior_back_photo = Column(String(255), nullable=True)
    
    # Связь с водителем
    driver = relationship("Driver", backref="driver_cars")


class DriverDocuments(Base):
    __tablename__ = "driver_documents"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    passport_front = Column(String(255), nullable=True)
    passport_back = Column(String(255), nullable=True)
    license_front = Column(String(255), nullable=True)
    license_back = Column(String(255), nullable=True)
    driver_with_license = Column(String(255), nullable=True)
    is_verified = Column(Boolean, default=False)
    verification_date = Column(DateTime, nullable=True)
    
    # Связь с водителем
    driver = relationship("Driver", backref="documents")


class DriverVerification(Base):
    __tablename__ = "driver_verifications"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    status = Column(String(20), default="pending")  # accepted, rejected, pending
    verification_type = Column(String(50), nullable=True)
    comment = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    verified_at = Column(DateTime, nullable=True)
    
    # Связь с водителем
    driver = relationship("Driver", backref="verifications") 