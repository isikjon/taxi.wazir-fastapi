from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import date, datetime
from .models import TokenResponse

# Car schemas
class CarBase(BaseModel):
    brand: str
    model: str
    year: int
    transmission: str
    has_booster: bool = False
    has_child_seat: bool = False
    tariff: str
    license_plate: str
    vin: str
    service_type: str
    color: Optional[str] = None
    sts: Optional[str] = None
    photo_front: Optional[str] = None
    photo_rear: Optional[str] = None
    photo_right: Optional[str] = None
    photo_left: Optional[str] = None
    photo_interior_front: Optional[str] = None
    photo_interior_rear: Optional[str] = None

class CarCreate(CarBase):
    pass

class Car(CarBase):
    id: int
    driver_id: int

    class Config:
        from_attributes = True

# Driver schemas
class DriverBase(BaseModel):
    full_name: str
    birth_date: date
    callsign: str
    unique_id: str = Field(..., min_length=20, max_length=20)
    city: str
    driver_license_number: str
    driver_license_issue_date: Optional[date] = None
    balance: float = 0.0
    tariff: str
    taxi_park: Optional[str] = None
    phone: Optional[str] = None
    is_mobile_registered: Optional[bool] = False
    registration_date: Optional[datetime] = None
    address: Optional[str] = None

    # Валидатор для проверки телефона
    @validator('phone')
    def phone_must_be_valid(cls, v):
        if v is not None and not v.replace('+', '').isdigit():
            raise ValueError('Телефон должен содержать только цифры')
        return v

class DriverCreate(DriverBase):
    pass

class Driver(DriverBase):
    id: int
    cars: List[Car] = []

    class Config:
        from_attributes = True

# Order schemas
class OrderBase(BaseModel):
    order_number: str = Field(..., min_length=1, description="Номер заказа")
    time: str = Field(..., min_length=1, description="Время заказа")
    origin: str = Field(..., min_length=1, description="Адрес отправления")
    destination: str = Field(..., min_length=1, description="Адрес назначения")
    driver_id: Optional[int] = None  # Водитель может быть не назначен при создании заказа
    status: Optional[str] = "Ожидает водителя"
    price: Optional[float] = None
    tariff: Optional[str] = Field(..., min_length=1, description="Тариф")
    notes: Optional[str] = None
    payment_method: Optional[str] = Field(..., min_length=1, description="Способ оплаты")
    
    # Валидаторы
    @validator('order_number')
    def order_number_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Номер заказа не может быть пустым')
        return v.strip()
    
    @validator('origin')
    def origin_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Адрес отправления не может быть пустым')
        return v.strip()
    
    @validator('destination')
    def destination_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Адрес назначения не может быть пустым')
        return v.strip()
    
    @validator('tariff')
    def tariff_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Тариф не может быть пустым')
        return v.strip()
    
    @validator('payment_method')
    def payment_method_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Способ оплаты не может быть пустым')
        return v.strip()

class OrderCreate(OrderBase):
    pass

class Order(OrderBase):
    id: int
    created_at: datetime
    driver: Optional[Driver] = None

    class Config:
        from_attributes = True

# Message schemas
class MessageBase(BaseModel):
    content: str
    is_broadcast: bool = False
    recipient_id: Optional[int] = None  # None для общей рассылки

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: int
    sender_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True

# DriverUser schemas
class DriverUserBase(BaseModel):
    phone: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class DriverUserCreate(DriverUserBase):
    pass


class DriverUserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_verified: Optional[bool] = None
    driver_id: Optional[int] = None


class DriverUser(DriverUserBase):
    id: int
    is_verified: bool
    date_registered: datetime
    last_login: Optional[datetime] = None
    driver_id: Optional[int] = None

    class Config:
        from_attributes = True 