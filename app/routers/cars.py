from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import shutil
from .. import crud, models, schemas
from ..database import get_db

router = APIRouter(
    prefix="/cars",
    tags=["cars"],
    responses={404: {"description": "Car not found"}},
)

# Создаём директорию для хранения фотографий, если её нет
os.makedirs("uploads/cars", exist_ok=True)

@router.post("/", response_model=schemas.Car, status_code=status.HTTP_201_CREATED)
def create_car(driver_id: int, car: schemas.CarCreate, db: Session = Depends(get_db)):
    # Проверяем, существует ли водитель
    db_driver = crud.get_driver(db, driver_id=driver_id)
    if db_driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Проверяем, существует ли автомобиль с таким же VIN
    db_car = crud.get_car_by_vin(db, vin=car.vin)
    if db_car:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Car with this VIN already exists"
        )
    
    # Проверяем, существует ли автомобиль с таким же государственным номером
    db_car = crud.get_car_by_license_plate(db, license_plate=car.license_plate)
    if db_car:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Car with this license plate already exists"
        )
    
    return crud.create_car(db=db, car=car, driver_id=driver_id)

@router.get("/", response_model=List[schemas.Car])
def read_cars(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    cars = crud.get_cars(db, skip=skip, limit=limit)
    return cars

@router.get("/{car_id}", response_model=schemas.Car)
def read_car(car_id: int, db: Session = Depends(get_db)):
    db_car = crud.get_car(db, car_id=car_id)
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    return db_car

@router.get("/driver/{driver_id}", response_model=List[schemas.Car])
def read_driver_cars(driver_id: int, db: Session = Depends(get_db)):
    # Проверяем, существует ли водитель
    db_driver = crud.get_driver(db, driver_id=driver_id)
    if db_driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    cars = crud.get_driver_cars(db, driver_id=driver_id)
    return cars

@router.put("/{car_id}", response_model=schemas.Car)
def update_car_info(car_id: int, car: schemas.CarCreate, db: Session = Depends(get_db)):
    db_car = crud.get_car(db, car_id=car_id)
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    
    # Проверяем, не занят ли VIN другим автомобилем
    if car.vin != db_car.vin:
        existing_car = crud.get_car_by_vin(db, vin=car.vin)
        if existing_car:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Car with this VIN already exists"
            )
    
    # Проверяем, не занят ли государственный номер другим автомобилем
    if car.license_plate != db_car.license_plate:
        existing_car = crud.get_car_by_license_plate(db, license_plate=car.license_plate)
        if existing_car:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Car with this license plate already exists"
            )
    
    return crud.update_car(db=db, car_id=car_id, car_data=car)

@router.delete("/{car_id}", response_model=schemas.Car)
def delete_car(car_id: int, db: Session = Depends(get_db)):
    db_car = crud.get_car(db, car_id=car_id)
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    return crud.delete_car(db=db, car_id=car_id)

@router.post("/{car_id}/upload-photo/{photo_type}")
async def upload_car_photo(
    car_id: int, 
    photo_type: str, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db)
):
    # Проверка существования автомобиля
    db_car = crud.get_car(db, car_id=car_id)
    if db_car is None:
        raise HTTPException(status_code=404, detail="Car not found")
    
    # Проверка типа фотографии
    valid_photo_types = ["front", "rear", "right", "left", "interior_front", "interior_rear"]
    if photo_type not in valid_photo_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid photo type. Must be one of: {', '.join(valid_photo_types)}"
        )
    
    # Создаем директорию для фотографий этого автомобиля
    car_dir = f"uploads/cars/{car_id}"
    os.makedirs(car_dir, exist_ok=True)
    
    # Определяем имя файла
    file_extension = os.path.splitext(file.filename)[1]
    file_path = f"{car_dir}/{photo_type}{file_extension}"
    
    # Сохраняем файл
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # Обновляем путь к фото в базе данных
    setattr(db_car, f"photo_{photo_type}", file_path)
    db.commit()
    
    return {"filename": file.filename, "photo_type": photo_type, "path": file_path} 