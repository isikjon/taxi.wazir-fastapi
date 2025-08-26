from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from .. import crud, models, schemas
from ..database import get_db


router = APIRouter(
    prefix="/orders",
    tags=["orders"],
    responses={404: {"description": "Order not found"}},
)

# Статические маршруты должны быть первыми

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

@router.get("/test-endpoint")
def test_endpoint():
    """Тестовый endpoint для проверки работы роутера"""
    return {"message": "Orders router works!", "timestamp": datetime.now().isoformat()}

@router.post("/test-complete-order")
def test_complete_order():
    """Простой тестовый endpoint для проверки POST запросов"""
    return {"message": "POST endpoint works!", "timestamp": datetime.now().isoformat()}

@router.post("/complete-with-progress-debug")
def complete_order_with_progress_debug(request: dict):
    """Отладочная версия эндпоинта без обращения к БД"""
    print("🔍 DEBUG: Вход в функцию complete_order_with_progress_debug")
    print(f"🔍 DEBUG: Получен request: {request}")
    
    # Просто возвращаем успешный ответ для тестирования
    return {
        "success": True,
        "message": "Debug endpoint works!",
        "received_data": request,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/complete-with-progress")
def complete_order_with_progress(
    request: dict,
    db: Session = Depends(get_db)
):
    """Завершение заказа с расчетом фактической оплаты по прогрессу"""
    print("🚨 НАЧАЛО ФУНКЦИИ complete_order_with_progress")
    print(f"🚨 Получен request: {request}")
    
    # Извлекаем данные из словаря
    order_id = request.get('order_id')
    driver_id = request.get('driver_id')
    completion_type = request.get('completion_type')
    final_latitude = request.get('final_latitude')
    final_longitude = request.get('final_longitude')
    
    # Валидация обязательных параметров
    if not order_id or not driver_id or not completion_type:
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: order_id, driver_id, completion_type"
        )
    
    try:
        # Логируем входящий запрос
        print(f"📥 Получен запрос на завершение заказа: order_id={order_id}, driver_id={driver_id}, type={completion_type}")
        
        # Находим заказ
        db_order = crud.get_order(db, order_id=order_id)
        if not db_order:
            raise HTTPException(status_code=404, detail="Order not found")
            
        # Проверяем, что заказ назначен на этого водителя
        if db_order.driver_id != driver_id:
            raise HTTPException(status_code=403, detail="Order not assigned to this driver")
        
        # Проверяем, что заказ не завершен
        if db_order.status == "Завершен":
            raise HTTPException(status_code=400, detail="Order already completed")
        
        # Находим водителя
        db_driver = crud.get_driver(db, driver_id=driver_id)
        if not db_driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        # Обновляем позицию если указана
        if final_latitude and final_longitude:
            db_driver.current_lat = final_latitude
            db_driver.current_lng = final_longitude
            db_driver.last_location_update = datetime.now()
        
        # Рассчитываем фактическую оплату
        base_price = float(db_order.price) if db_order.price else 433.0  # Цена по умолчанию
        
        if completion_type == "full":
            # Полное завершение - 100% оплаты
            db_order.actual_price = base_price
            db_order.progress_percentage = 100.0
        else:
            # Частичное завершение - оплата по прогрессу (минимум 30%)
            progress = db_order.progress_percentage if db_order.progress_percentage and db_order.progress_percentage > 0 else 30.0
            db_order.actual_price = round(base_price * (progress / 100))
            db_order.progress_percentage = progress
        
        # Обновляем статус заказа
        db_order.status = "Завершен"
        db_order.completed_at = datetime.now()
        
        # Обновляем баланс водителя
        if db_order.actual_price:
            db_driver.balance = float(db_driver.balance or 0) + float(db_order.actual_price)
        
        db.commit()
        db.refresh(db_order)
        db.refresh(db_driver)
        
        final_progress = db_order.progress_percentage or 30.0
        final_payment = db_order.actual_price or 0.0
        
        result = {
            "success": True,
            "order_id": db_order.id,
            "completion_type": completion_type,
            "progress_percentage": final_progress,
            "base_price": base_price,
            "actual_payment": final_payment,
            "driver_balance": db_driver.balance,
            "message": f"Заказ завершен на {final_progress:.1f}%. Получено: {final_payment:.2f} сом"
        }
        
        print(f"✅ Заказ успешно завершен: {result}")
        return result
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        print(f"❌ Ошибка при завершении заказа: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка сервера: {str(e)}"
        )

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

# Динамические маршруты должны быть последними

@router.get("/{order_id}", response_model=schemas.Order)
def read_order(order_id: int, db: Session = Depends(get_db)):
    db_order = crud.get_order(db, order_id=order_id)
    if db_order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return db_order

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