from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Float, Date, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from .database import Base

class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, index=True)
    unique_id = Column(String(20), unique=True, index=True)
    full_name = Column(String(255), nullable=False)
    birthdate = Column(Date, nullable=False)
    callsign = Column(String(50), nullable=False)
    city = Column(String(100), nullable=False)
    driver_license_number = Column(String(50), unique=True, nullable=False)
    driver_license_issue_date = Column(Date, nullable=True)
    balance = Column(Float, default=0.0)
    tariff = Column(String(50), nullable=False)  # Бюджетный, Стандартный, Бизнес, Люкс
    taxi_park = Column(String(100), nullable=True)
    phone = Column(String(50), nullable=True)  # Номер телефона водителя
    status = Column(String(20), default="pending")  # accepted, rejected, pending
    
    cars = relationship("Car", back_populates="driver")
    
    orders = relationship("Order", back_populates="driver")

    transactions = relationship("BalanceTransaction", back_populates="driver")
    
    @property
    def car(self):
        """Возвращает первый автомобиль водителя (для обратной совместимости)"""
        return self.cars[0] if self.cars else None


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
    tariff = Column(String(50), nullable=False)  # Бюджетный, Стандартный, Бизнес, Люкс
    license_plate = Column(String(50), unique=True, nullable=False)
    vin = Column(String(50), unique=True, nullable=False)
    service_type = Column(String(50), nullable=False)  # Грузоперевозка, Такси
    color = Column(String(50), nullable=True)  # Цвет автомобиля
    
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
    time = Column(String(5), nullable=False)  # чч:мм
    origin = Column(Text, nullable=False)  # Откуда
    destination = Column(Text, nullable=False)  # Куда
    driver_id = Column(Integer, ForeignKey("drivers.id"))
    created_at = Column(DateTime, server_default=func.now())
    status = Column(String(50), default="Свободен")  # Свободен, Занят, Отменен
    price = Column(Float, nullable=True)  # Стоимость поездки
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