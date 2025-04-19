from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, datetime

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
        orm_mode = True

# Driver schemas
class DriverBase(BaseModel):
    full_name: str
    birthdate: date
    callsign: str
    unique_id: str = Field(..., min_length=20, max_length=20)
    city: str
    driver_license_number: str
    driver_license_issue_date: Optional[date] = None
    balance: float = 0.0
    tariff: str
    taxi_park: Optional[str] = None

class DriverCreate(DriverBase):
    pass

class Driver(DriverBase):
    id: int
    cars: List[Car] = []

    class Config:
        orm_mode = True

# Order schemas
class OrderBase(BaseModel):
    time: str
    origin: str
    destination: str
    driver_id: int
    status: Optional[str] = "Свободен"
    price: Optional[float] = None
    notes: Optional[str] = None
    payment_method: Optional[str] = None

class OrderCreate(OrderBase):
    pass

class Order(OrderBase):
    id: int
    created_at: datetime
    driver: Optional[Driver] = None

    class Config:
        orm_mode = True

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
        orm_mode = True 