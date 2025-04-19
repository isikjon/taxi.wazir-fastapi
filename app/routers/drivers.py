from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from .. import crud, models, schemas
from ..database import get_db

router = APIRouter(
    prefix="/drivers",
    tags=["drivers"],
    responses={404: {"description": "Driver not found"}},
)

@router.post("/", response_model=schemas.Driver, status_code=status.HTTP_201_CREATED)
def create_driver(driver: schemas.DriverCreate, db: Session = Depends(get_db)):
    # Проверяем, существует ли водитель с таким же уникальным ID
    db_driver = crud.get_driver_by_unique_id(db, unique_id=driver.unique_id.upper())
    if db_driver:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver with this unique ID already exists"
        )
    
    # Проверяем, существует ли водитель с таким же номером ВУ
    db_driver_by_license = crud.get_driver_by_license(db, license_number=driver.driver_license_number)
    if db_driver_by_license:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Driver with this license number already exists"
        )
    
    return crud.create_driver(db=db, driver=driver)

@router.get("/", response_model=List[schemas.Driver])
def read_drivers(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    drivers = crud.get_drivers(db, skip=skip, limit=limit)
    return drivers

@router.get("/{driver_id}", response_model=schemas.Driver)
def read_driver(driver_id: int, db: Session = Depends(get_db)):
    db_driver = crud.get_driver(db, driver_id=driver_id)
    if db_driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return db_driver

@router.get("/unique/{unique_id}", response_model=schemas.Driver)
def read_driver_by_unique_id(unique_id: str, db: Session = Depends(get_db)):
    db_driver = crud.get_driver_by_unique_id(db, unique_id=unique_id.upper())
    if db_driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return db_driver

@router.put("/{driver_id}", response_model=schemas.Driver)
def update_driver_info(driver_id: int, driver: schemas.DriverCreate, db: Session = Depends(get_db)):
    db_driver = crud.get_driver(db, driver_id=driver_id)
    if db_driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    
    # Проверяем, не занят ли уникальный ID другим водителем
    if driver.unique_id.upper() != db_driver.unique_id:
        existing_driver = crud.get_driver_by_unique_id(db, unique_id=driver.unique_id.upper())
        if existing_driver:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Driver with this unique ID already exists"
            )
    
    # Проверяем, не занят ли номер ВУ другим водителем
    if driver.driver_license_number != db_driver.driver_license_number:
        existing_driver = crud.get_driver_by_license(db, license_number=driver.driver_license_number)
        if existing_driver:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Driver with this license number already exists"
            )
    
    return crud.update_driver(db=db, driver_id=driver_id, driver_data=driver)

@router.delete("/{driver_id}", response_model=schemas.Driver)
def delete_driver(driver_id: int, db: Session = Depends(get_db)):
    """
    Удаляет водителя по ID.
    
    - **driver_id**: ID водителя для удаления
    
    Возвращает данные удаленного водителя.
    """
    db_driver = crud.get_driver(db, driver_id=driver_id)
    if db_driver is None:
        raise HTTPException(status_code=404, detail="Driver not found")
    return crud.delete_driver(db=db, driver_id=driver_id) 