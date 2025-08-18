from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from .. import crud, models, schemas
from ..database import get_db

router = APIRouter(
    prefix="/orders",
    tags=["orders"],
    responses={404: {"description": "Order not found"}},
)

@router.post("/", response_model=schemas.Order, status_code=status.HTTP_201_CREATED)
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    # Проверяем, существует ли водитель (только если он указан)
    if order.driver_id is not None:
        db_driver = crud.get_driver(db, driver_id=order.driver_id)
        if db_driver is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Driver not found"
            )
    
    # Валидация формата времени (чч:мм)
    try:
        hours, minutes = order.time.split(":")
        if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
            raise ValueError("Invalid time format")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid time format. Must be in 'HH:MM' format (24-hour)"
        )
    
    return crud.create_order(db=db, order=order)

@router.get("/", response_model=List[schemas.Order])
def read_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    orders = crud.get_orders(db, skip=skip, limit=limit)
    return orders

@router.get("/{order_id}", response_model=schemas.Order)
def read_order(order_id: int, db: Session = Depends(get_db)):
    db_order = crud.get_order(db, order_id=order_id)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

@router.get("/driver/{driver_id}", response_model=List[schemas.Order])
def read_driver_orders(driver_id: int, db: Session = Depends(get_db)):
    # Проверяем, существует ли водитель
    db_driver = crud.get_driver(db, driver_id=driver_id)
    if db_driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    orders = crud.get_driver_orders(db, driver_id=driver_id)
    return orders

@router.put("/{order_id}", response_model=schemas.Order)
def update_order_info(order_id: int, order: schemas.OrderCreate, db: Session = Depends(get_db)):
    db_order = crud.get_order(db, order_id=order_id)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Проверяем, существует ли водитель
    db_driver = crud.get_driver(db, driver_id=order.driver_id)
    if db_driver is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Driver not found"
        )
    
    # Валидация формата времени (чч:мм)
    try:
        hours, minutes = order.time.split(":")
        if not (0 <= int(hours) <= 23 and 0 <= int(minutes) <= 59):
            raise ValueError("Invalid time format")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid time format. Must be in 'HH:MM' format (24-hour)"
        )
    
    return crud.update_order(db=db, order_id=order_id, order_data=order)

@router.delete("/{order_id}", response_model=schemas.Order)
def delete_order(order_id: int, db: Session = Depends(get_db)):
    db_order = crud.get_order(db, order_id=order_id)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return crud.delete_order(db=db, order_id=order_id)

@router.get("/{order_id}/status")
def get_order_status(order_id: int, db: Session = Depends(get_db)):
    """Получить статус заказа для отслеживания"""
    db_order = crud.get_order(db, order_id=order_id)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return {
        "order_id": order_id,
        "status": db_order.status,
        "driver_id": db_order.driver_id,
        "created_at": db_order.created_at,
        "updated_at": getattr(db_order, 'updated_at', None)
    } 