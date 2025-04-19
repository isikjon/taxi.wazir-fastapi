from fastapi import FastAPI, Depends, Request, Response, Query, Form, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import os
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from math import ceil
from datetime import datetime, timedelta
import random
from pydantic import BaseModel
import uuid
from pathlib import Path
import secrets
from starlette.middleware.base import BaseHTTPMiddleware

from .database import engine, Base, get_db
from .routers import drivers, cars, orders, messages
from . import models, crud, schemas

# Создаем все таблицы в базе данных
Base.metadata.create_all(bind=engine)

# Создаем директории для загрузки файлов
os.makedirs("uploads", exist_ok=True)
os.makedirs("uploads/cars", exist_ok=True)

app = FastAPI(
    title="WAZIR MTT API",
    description="API для управления водителями и заказами WAZIR MTT",
    version="1.0.0"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене заменить на список конкретных доменов
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем статические файлы
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Настраиваем шаблоны Jinja2
templates = Jinja2Templates(directory="app/templates")

# Подключаем API роутеры
app.include_router(drivers.router)
app.include_router(cars.router)
app.include_router(orders.router)
app.include_router(messages.router)

# Middleware для проверки авторизации
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Разрешаем доступ к статическим файлам и странице логина
        if request.url.path.startswith("/static") or request.url.path == "/login":
            return await call_next(request)
            
        # Проверяем авторизацию только для маршрутов /disp/
        if request.url.path.startswith("/disp/"):
            session = request.cookies.get("session")
            if not session:
                return RedirectResponse(url="/login", status_code=303)
        
        return await call_next(request)

app.add_middleware(AuthMiddleware)

# Модель для запроса пополнения баланса
class BalanceAddRequest(BaseModel):
    driver_id: int
    amount: int

# Маршруты для диспетчерской панели
@app.get("/", response_class=HTMLResponse)
@app.get("/disp", response_class=HTMLResponse)
async def disp_home(
    request: Request,
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    status: Optional[str] = None,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1)
):
    """Главная страница диспетчерской с отображением заказов"""
    # Получаем все заказы из БД
    all_orders = crud.get_orders(db)
    all_drivers = crud.get_drivers(db)
    
    # Фильтрация заказов
    filtered_orders = all_orders.copy() if all_orders else []
    
    # Фильтр по поиску (ищем в номере телефона, адресах и позывном)
    if search:
        search_lower = search.lower()
        filtered_orders = [
            order for order in filtered_orders if (
                (hasattr(order, 'driver') and 
                 order.driver and 
                 hasattr(order.driver, 'phone') and 
                 search_lower in str(order.driver.phone).lower()) or
                (hasattr(order, 'origin') and 
                 order.origin and 
                 search_lower in order.origin.lower()) or
                (hasattr(order, 'destination') and 
                 order.destination and 
                 search_lower in order.destination.lower()) or
                (hasattr(order, 'driver') and 
                 order.driver and 
                 hasattr(order.driver, 'callsign') and 
                 search_lower in order.driver.callsign.lower())
            )
        ]
    
    # Фильтр по статусу
    if status:
        filtered_orders = [
            order for order in filtered_orders if
            (hasattr(order, 'status') and order.status == status)
        ]
    
    # Фильтр по конкретной дате
    if date and date != "all":
        filtered_orders = [
            order for order in filtered_orders if
            (hasattr(order, 'created_at') and 
             order.created_at.strftime('%d.%m.%y') == date)
        ]
    
    # Фильтр по диапазону дат
    if start_date and end_date:
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
            end = end.replace(hour=23, minute=59, second=59)  # До конца дня
            
            filtered_orders = [
                order for order in filtered_orders if
                (hasattr(order, 'created_at') and 
                 start <= order.created_at <= end)
            ]
        except ValueError:
            # В случае некорректного формата дат, игнорируем этот фильтр
            pass
    
    # Проверяем наличие хотя бы одного примененного фильтра
    is_filtered = bool(search) or bool(status) or bool(date) or (bool(start_date) and bool(end_date))
    
    # Подсчет количества заказов и извлечение доступных дат для фильтра
    total_orders = len(filtered_orders)
    available_dates = sorted(set(
        order.created_at.strftime('%d.%m.%y') 
        for order in all_orders 
        if hasattr(order, 'created_at')
    ))
    
    # Расчет суммарного баланса всех водителей
    total_balance = sum(driver.balance for driver in all_drivers if hasattr(driver, 'balance'))
    
    # Пагинация
    items_per_page = 10
    total_pages = max(1, ceil(total_orders / items_per_page))
    page = min(max(1, page), total_pages)
    
    # Получаем заказы для текущей страницы
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_orders)
    paged_orders = filtered_orders[start_idx:end_idx] if filtered_orders else []
    
    # Данные для шаблона
    template_data = {
        "current_page": "home",
        "orders": paged_orders,
        "total_orders": total_orders,
        "total_drivers": len(all_drivers),
        "total_balance": f"{total_balance:.0f}",
        
        # Параметры фильтрации
        "search": search,
        "status_filter": status,
        "date_filter": date,
        "start_date": start_date,
        "end_date": end_date,
        "available_dates": available_dates,
        
        # Параметры пагинации
        "page": page,
        "total_pages": total_pages,
        
        # Флаг применения фильтров
        "is_filtered": is_filtered
    }
    
    return templates.TemplateResponse("disp/index.html", {"request": request, **template_data})

@app.get("/disp/analytics", response_class=HTMLResponse)
async def disp_analytics(request: Request, db: Session = Depends(get_db)):
    """Страница аналитики"""
    
    # Получаем данные о водителях, машинах и заказах из БД
    all_drivers = crud.get_drivers(db)
    all_cars = crud.get_cars(db)
    
    # Расчет суммарного баланса всех водителей
    total_balance = 0
    if all_drivers:
        # Суммируем балансы всех водителей
        for driver in all_drivers:
            total_balance += driver.balance
    
    # Формируем данные для диаграмм
    analytics_data = {
        "current_page": "analytics",
        "balance": f"{total_balance:.0f}",
        
        # Количество водителей и машин для диаграмм
        "total_drivers": len(all_drivers),
        "total_cars": len(all_cars),
        
        # Данные для старых диаграмм (оставляем для совместимости)
        "total_orders": 100,
        "completed_orders": 55,
        "cancelled_orders": 45,
        "completed_percentage": 55,
        "total_types": 50,
        "taxipark_orders": 30,
        "platform_orders": 18,
        "bort_orders": 2,
        "order_types_percentage": 70,
        "total_categories": 50,
        "economy_orders": 45,
        "comfort_orders": 5,
        "categories_percentage": 95
    }
    
    return templates.TemplateResponse(
        "disp/analytics.html", 
        {"request": request, **analytics_data}
    )

@app.get("/disp/cars", response_class=HTMLResponse)
async def disp_cars(
    request: Request, 
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    brand: Optional[str] = None,
    model: Optional[str] = None,
    color: Optional[str] = None,
    year: Optional[int] = None,
    page: int = Query(1, ge=1)
):
    """Страница автомобилей"""
    
    # Получаем данные о водителях для расчета баланса
    all_drivers = crud.get_drivers(db)
    
    # Расчет суммарного баланса всех водителей
    total_balance = 0
    if all_drivers:
        for driver in all_drivers:
            total_balance += driver.balance
    
    # Получаем все автомобили
    all_cars = crud.get_cars(db)
    
    # Фильтрация автомобилей
    filtered_cars = []
    
    # Если есть автомобили, выполняем фильтрацию
    if all_cars:
        filtered_cars = all_cars
        
        # Применяем фильтры, если они указаны
        if status:
            filtered_cars = [car for car in filtered_cars if car.status == status]
        
        if brand:
            filtered_cars = [car for car in filtered_cars if car.brand == brand]
        
        if model:
            filtered_cars = [car for car in filtered_cars if car.model == model]
        
        if color:
            filtered_cars = [car for car in filtered_cars if car.color == color]
        
        if year:
            filtered_cars = [car for car in filtered_cars if car.year == year]
    
    # Настройки пагинации
    items_per_page = 10
    total_cars = len(filtered_cars)
    total_pages = (total_cars + items_per_page - 1) // items_per_page
    
    # Корректируем текущую страницу, если она вне диапазона
    if page > total_pages and total_pages > 0:
        page = total_pages
    
    # Вычисляем индексы для среза списка автомобилей
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, total_cars)
    
    # Получаем срез списка для текущей страницы
    paginated_cars = filtered_cars[start_idx:end_idx] if filtered_cars else []
    
    # Собираем уникальные значения для фильтров
    brands = list(set(car.brand for car in all_cars)) if all_cars else []
    models = list(set(car.model for car in all_cars)) if all_cars else []
    colors = list(set(car.color for car in all_cars)) if all_cars else []
    years = list(set(car.year for car in all_cars)) if all_cars else []
    
    # Формируем данные для шаблона
    template_data = {
        "current_page": "cars",
        "balance": f"{total_balance:.0f}",
        "cars": paginated_cars,
        "total_cars": total_cars,
        "brands": brands,
        "models": models,
        "colors": colors,
        "years": years,
        "current_page_num": page,
        "total_pages": total_pages,
        
        # Фильтры для сохранения состояния
        "selected_status": status,
        "selected_brand": brand,
        "selected_model": model, 
        "selected_color": color,
        "selected_year": year
    }
    
    return templates.TemplateResponse(
        "disp/cars.html", 
        {"request": request, **template_data}
    )

@app.get("/disp/drivers", response_class=HTMLResponse)
async def disp_drivers(
    request: Request, 
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    status: Optional[str] = None,
    state: Optional[str] = None,
    page: int = 1
):
    """Страница водителей с поддержкой фильтрации и пагинации"""
    # Получаем всех водителей
    drivers = crud.get_drivers(db)
    
    # Применяем фильтры, если они указаны
    filtered_drivers = drivers.copy() if drivers else []
    
    if search:
        search = search.lower()
        filtered_drivers = [
            d for d in filtered_drivers if (
                search in d.full_name.lower() or 
                search in getattr(d, 'callsign', '').lower() or
                search in str(getattr(d, 'driver_license_number', '')).lower()
            )
        ]
    
    if status:
        status = status.lower()
        filtered_drivers = [
            d for d in filtered_drivers if 
            (status == 'занят' and getattr(d, 'is_busy', True)) or
            (status == 'свободен' and not getattr(d, 'is_busy', True))
        ]
    
    if state:
        state = state.lower()
        filtered_drivers = [
            d for d in filtered_drivers if
            getattr(d, 'status', 'работает').lower() == state
        ]
    
    # Фильтры
    is_filtered = bool(search) or bool(status) or bool(state)
    
    # Подсчет метрик для отфильтрованных данных
    total_drivers = len(filtered_drivers)
    total_balance = sum(driver.balance for driver in filtered_drivers) if filtered_drivers else 0
    available_drivers = len([d for d in filtered_drivers if getattr(d, 'is_busy', False) == False])
    busy_drivers = total_drivers - available_drivers
    
    # Пагинация
    items_per_page = 10
    total_pages = max(1, ceil(total_drivers / items_per_page))
    page = min(max(1, page), total_pages)
    
    # Получаем водителей для текущей страницы
    offset = (page - 1) * items_per_page
    limit = items_per_page
    paged_drivers = filtered_drivers[offset:offset+limit] if filtered_drivers else []
    
    return templates.TemplateResponse(
        "disp/drivers.html", 
        {
            "request": request, 
            "drivers": paged_drivers,
            "total_drivers": total_drivers,
            "total_balance": total_balance,
            "available_drivers": available_drivers,
            "busy_drivers": busy_drivers,
            "page": page,
            "total_pages": total_pages,
            "is_filtered": is_filtered,
            "search": search,
            "status": status,
            "state": state
        }
    )

@app.get("/disp/drivers_control", response_class=HTMLResponse)
async def disp_drivers_control(
    request: Request, 
    db: Session = Depends(get_db),
    search: Optional[str] = None,
    status: Optional[str] = None
):
    """Страница фото контроля водителей с фильтрацией и поиском"""
    # Базовый запрос всех водителей
    query = db.query(models.Driver)
    
    # Применяем фильтры, если они указаны
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                models.Driver.full_name.ilike(search_term),
                models.Driver.callsign.ilike(search_term),
                models.Driver.phone.ilike(search_term)
            )
        )
    
    # Получаем всех водителей для базового списка
    all_drivers = query.all()
    
    # Разделяем водителей на принятых и отклоненных для правильного подсчета
    accepted_drivers = [d for d in all_drivers if getattr(d, 'status', None) == 'accepted']
    rejected_drivers = [d for d in all_drivers if getattr(d, 'status', None) == 'rejected']
    pending_drivers = [d for d in all_drivers if getattr(d, 'status', None) == 'pending' or getattr(d, 'status', None) is None]
    
    # Если указан статус, применяем фильтр к исходному запросу
    if status:
        query = query.filter(models.Driver.status == status)
        # Получаем отфильтрованных водителей
        filtered_drivers = query.all()
        
        # В зависимости от статуса, заполняем соответствующий список фильтрованными данными
        if status == 'accepted':
            accepted_drivers = filtered_drivers
        elif status == 'rejected':
            rejected_drivers = filtered_drivers
        elif status == 'pending':
            pending_drivers = filtered_drivers
    
    # Получаем статистику
    total_drivers = len(all_drivers)
    available_drivers = len([d for d in all_drivers if hasattr(d, 'is_busy') and not d.is_busy])
    busy_drivers = total_drivers - available_drivers
    
    # Рассчитываем общий баланс
    total_balance = sum(getattr(driver, 'balance', 0) for driver in all_drivers)
    
    # Считаем количество отклоненных водителей для отображения
    rejected_count = len(rejected_drivers)
    
    return templates.TemplateResponse(
        "disp/drivers_control.html",
        {
            "request": request,
            "current_page": "drivers_control",
            "all_drivers": all_drivers,
            "accepted_drivers": accepted_drivers,
            "rejected_drivers": rejected_drivers,
            "pending_drivers": pending_drivers,
            "total_drivers": total_drivers,
            "available_drivers": available_drivers,
            "busy_drivers": busy_drivers,
            "total_balance": f"{total_balance:.0f}",
            "search": search,
            "status": status,
            "rejected_count": rejected_count
        }
    )

@app.post("/api/drivers/{driver_id}/verify", response_class=JSONResponse)
async def verify_driver(driver_id: int, status: str = Query(...), db: Session = Depends(get_db)):
    """API для верификации водителя (принять/отклонить)"""
    try:
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return JSONResponse(status_code=404, content={"success": False, "detail": "Водитель не найден"})
        
        # Обновляем статус верификации
        if status in ["accepted", "rejected"]:
            driver.status = status
            db.commit()
            return {"success": True}
        else:
            return JSONResponse(status_code=400, content={"success": False, "detail": "Недопустимый статус"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"success": False, "detail": str(e)})

@app.get("/api/drivers/{driver_id}/details", response_class=JSONResponse)
async def get_driver_details(driver_id: int, db: Session = Depends(get_db)):
    """API для получения полной информации о водителе и его автомобиле"""
    try:
        # Получаем водителя с первым автомобилем
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return JSONResponse(status_code=404, content={"detail": "Водитель не найден"})
        
        # Получаем автомобиль водителя
        car = db.query(models.Car).filter(models.Car.driver_id == driver_id).first()
        
        # Формируем пути к фотографиям
        photo_paths = {
            "passport_front": f"/uploads/drivers/{driver_id}/passport_front.jpg" if hasattr(driver, "passport_front_path") and driver.passport_front_path else None,
            "passport_back": f"/uploads/drivers/{driver_id}/passport_back.jpg" if hasattr(driver, "passport_back_path") and driver.passport_back_path else None,
            "license_front": f"/uploads/drivers/{driver_id}/license_front.jpg" if hasattr(driver, "license_front_path") and driver.license_front_path else None,
            "license_back": f"/uploads/drivers/{driver_id}/license_back.jpg" if hasattr(driver, "license_back_path") and driver.license_back_path else None
        }
        
        # Добавляем фото автомобиля, если есть
        if car:
            photo_paths.update({
                "car_front": car.photo_front,
                "car_back": car.photo_rear,
                "car_right": car.photo_right,
                "car_left": car.photo_left,
                "car_interior_front": car.photo_interior_front,
                "car_interior_back": car.photo_interior_rear
            })
        
        # Определяем, создан ли водитель в диспетчерской
        # Если у водителя отсутствуют фотографии паспорта и вод. удостоверения, 
        # считаем что он создан в диспетчерской
        is_disp_created = not any([
            getattr(driver, "passport_front_path", None), 
            getattr(driver, "passport_back_path", None),
            getattr(driver, "license_front_path", None),
            getattr(driver, "license_back_path", None)
        ])
        
        # Собираем детальную информацию
        driver_data = {
            "id": driver.id,
            "full_name": driver.full_name,
            "callsign": getattr(driver, "callsign", ""),
            "phone": getattr(driver, "phone", ""),
            "city": getattr(driver, "city", ""),
            "birthdate": str(driver.birthdate) if hasattr(driver, "birthdate") else "",
            "driver_license": getattr(driver, "driver_license_number", ""),
            "driver_license_issue_date": str(driver.driver_license_issue_date) if hasattr(driver, "driver_license_issue_date") else "",
            "balance": getattr(driver, "balance", 0),
            "tariff": getattr(driver, "tariff", ""),
            "taxi_park": getattr(driver, "taxi_park", ""),
            "status": getattr(driver, "status", "pending"),
            "photos": photo_paths,
            "is_disp_created": is_disp_created
        }
        
        # Если есть автомобиль, добавляем его данные
        if car:
            car_data = {
                "id": car.id,
                "brand": car.brand,
                "model": car.model,
                "year": car.year,
                "color": getattr(car, "color", ""),
                "transmission": car.transmission,
                "license_plate": car.license_plate,
                "vin": car.vin,
                "has_booster": car.has_booster,
                "has_child_seat": car.has_child_seat,
                "tariff": car.tariff,
                "service_type": car.service_type
            }
            driver_data["car"] = car_data
        
        return driver_data
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})

@app.get("/disp/chat", response_class=HTMLResponse)
async def disp_chat(request: Request, db: Session = Depends(get_db)):
    """Страница чата с водителями"""
    # Получаем всех водителей из БД
    drivers = crud.get_drivers(db)
    
    # Расчет суммарного баланса всех водителей
    total_balance = 0
    if drivers:
        for driver in drivers:
            total_balance += driver.balance
    
    # Получаем количество свободных и занятых водителей
    available_drivers = 0
    busy_drivers = 0
    
    for driver in drivers:
        if hasattr(driver, 'status') and driver.status == 'Свободен':
            available_drivers += 1
        else:
            busy_drivers += 1
    
    template_data = {
        "request": request,
        "current_page": "chat",
        "drivers": drivers,
        "total_drivers": len(drivers),
        "available_drivers": available_drivers,
        "busy_drivers": busy_drivers,
        "balance": f"{total_balance:.0f}"
    }
    
    return templates.TemplateResponse("disp/chat.html", template_data)

@app.get("/disp/new_order", response_class=HTMLResponse)
async def disp_new_order(request: Request, db: Session = Depends(get_db)):
    """Страница создания нового заказа"""
    try:
        # Упрощенная обработка данных для избежания ошибок
        # 1. Базовые значения по умолчанию
        # Генерируем случайные номера заказа (9 цифр) и путевого листа (8 цифр)
        order_number = f"{random.randint(100000000, 999999999)}"
        route_number = f"{random.randint(10000000, 99999999)}"
        
        template_data = {
            "request": request,
            "current_page": "new_order",
            "drivers": [],
            "total_drivers": 0,
            "available_drivers": 0,
            "busy_drivers": 0,
            "balance": "0",
            "orders": [],
            "now": datetime.now(),
            "order_number": order_number,
            "route_number": route_number
        }
        
        # 2. Безопасно получаем водителей
        try:
            drivers_result = db.query(models.Driver).all()
            if drivers_result and isinstance(drivers_result, list):
                template_data["drivers"] = drivers_result
                template_data["total_drivers"] = len(drivers_result)
                
                # Вычисляем баланс и количество водителей
                total_balance = 0
                available_count = 0
                busy_count = 0
                
                for driver in drivers_result:
                    if hasattr(driver, 'balance'):
                        total_balance += float(driver.balance or 0)
                    
                    # Простая проверка статуса без доступа к orders
                    is_busy = False
                    if hasattr(driver, 'status') and driver.status == "Занят":
                        is_busy = True
                    
                    if is_busy:
                        busy_count += 1
                    else:
                        available_count += 1
                
                template_data["balance"] = f"{total_balance:.0f}"
                template_data["available_drivers"] = available_count
                template_data["busy_drivers"] = busy_count
        except Exception as e:
            print(f"Ошибка при получении данных о водителях: {e}")
        
        # 3. Безопасно получаем последние заказы
        try:
            orders_result = db.query(
                models.Order.id,
                models.Order.time,
                models.Order.origin,
                models.Order.destination,
                models.Order.driver_id,
                models.Order.created_at,
                models.Order.status,
                models.Order.price
            ).order_by(models.Order.created_at.desc()).limit(5).all()
            
            if orders_result and isinstance(orders_result, list):
                template_data["orders"] = orders_result
        except Exception as e:
            print(f"Ошибка при получении данных о заказах: {e}")
        
        # 4. Возвращаем шаблон с полученными (или дефолтными) данными
        return templates.TemplateResponse("disp/new_order.html", template_data)
    
    except Exception as e:
        print(f"Критическая ошибка в маршруте disp_new_order: {e}")
        # В случае ошибки возвращаем базовый шаблон с минимумом данных
        return templates.TemplateResponse("disp/new_order.html", {
            "request": request,
            "current_page": "new_order",
            "drivers": [],
            "total_drivers": 0,
            "available_drivers": 0,
            "busy_drivers": 0,
            "balance": "0",
            "orders": [],
            "now": datetime.now(),
            "order_number": f"{random.randint(100000000, 999999999)}",
            "route_number": f"{random.randint(10000000, 99999999)}"
        })

@app.get("/disp/pay_balance", response_class=HTMLResponse)
async def disp_pay_balance(
    request: Request,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    status: Optional[str] = None,
    date_filter: Optional[str] = None,
    search: Optional[str] = None
):
    """Страница пополнения баланса водителей"""
    items_per_page = 10
    
    # Базовый запрос водителей с присоединением автомобилей
    query = db.query(models.Driver).join(models.Car, models.Driver.id == models.Car.driver_id, isouter=True)
    
    # Применяем фильтры
    if status:
        query = query.filter(models.Driver.status == status)
    
    if date_filter:
        if date_filter == 'today':
            start_date = datetime.now().date()
            query = query.filter(models.Driver.created_at >= start_date)
        elif date_filter == 'week':
            start_date = datetime.now().date() - timedelta(days=7)
            query = query.filter(models.Driver.created_at >= start_date)
        elif date_filter == 'month':
            start_date = datetime.now().date() - timedelta(days=30)
            query = query.filter(models.Driver.created_at >= start_date)
    
    if search:
        search = f"%{search}%"
        query = query.filter(
            or_(
                models.Driver.full_name.ilike(search),
                models.Driver.callsign.ilike(search),
                models.Driver.phone.ilike(search),
                models.Car.license_plate.ilike(search)
            )
        )
    
    # Подсчет общего количества водителей
    total_drivers = query.count()
    
    # Подсчет общего баланса всех водителей
    total_balance = db.query(func.sum(models.Driver.balance)).scalar() or 0
    
    # Пагинация
    offset = (page - 1) * items_per_page
    drivers = query.offset(offset).limit(items_per_page).all()
    
    # Расчет общего количества страниц
    total_pages = (total_drivers + items_per_page - 1) // items_per_page
    
    return templates.TemplateResponse(
        "disp/pay_balance.html",
        {
            "request": request,
            "current_page": "pay_balance",
            "drivers": drivers,
            "page": page,
            "total_pages": total_pages,
            "total_drivers": total_drivers,
            "total_balance": total_balance,
            "status_filter": status,
            "date_filter": date_filter,
            "search": search
        }
    )

# API для пополнения баланса
@app.post("/api/balance/add/")
async def add_balance(request: BalanceAddRequest, db: Session = Depends(get_db)):
    try:
        # Проверяем существование водителя
        driver = db.query(models.Driver).filter(models.Driver.id == request.driver_id).first()
        if not driver:
            return {"success": False, "detail": "Водитель не найден"}
        
        # Проверяем корректность суммы
        if request.amount <= 0:
            return {"success": False, "detail": "Сумма должна быть положительной"}
        
        # Пополняем баланс
        driver.balance = driver.balance + request.amount
        
        # Создаем запись о транзакции
        transaction = models.BalanceTransaction(
            driver_id=driver.id,
            amount=request.amount,
            type="deposit",
            status="completed",
            description=f"Пополнение баланса водителя {driver.full_name}"
        )
        
        db.add(transaction)
        db.commit()
        
        return {"success": True, "new_balance": driver.balance}
    except Exception as e:
        db.rollback()
        return {"success": False, "detail": str(e)}

@app.get("/api/drivers/{driver_id}/photos")
async def get_driver_photos(driver_id: int, db: Session = Depends(get_db)):
    """API для получения фотографий водителя"""
    driver = crud.get_driver(db, driver_id=driver_id)
    if not driver:
        return JSONResponse(status_code=404, content={"detail": "Водитель не найден"})
    
    # Формируем пути к фотографиям
    photo_paths = {
        "passport_front": f"/uploads/drivers/{driver_id}/passport_front.jpg" if hasattr(driver, "passport_front_path") and driver.passport_front_path else None,
        "passport_back": f"/uploads/drivers/{driver_id}/passport_back.jpg" if hasattr(driver, "passport_back_path") and driver.passport_back_path else None,
        "license_front": f"/uploads/drivers/{driver_id}/license_front.jpg" if hasattr(driver, "license_front_path") and driver.license_front_path else None,
        "license_back": f"/uploads/drivers/{driver_id}/license_back.jpg" if hasattr(driver, "license_back_path") and driver.license_back_path else None,
        "car_front": f"/uploads/cars/{driver.car_id}/front.jpg" if hasattr(driver, "car_id") and driver.car_id else None,
        "car_back": f"/uploads/cars/{driver.car_id}/back.jpg" if hasattr(driver, "car_id") and driver.car_id else None,
        "car_right": f"/uploads/cars/{driver.car_id}/right.jpg" if hasattr(driver, "car_id") and driver.car_id else None,
        "car_left": f"/uploads/cars/{driver.car_id}/left.jpg" if hasattr(driver, "car_id") and driver.car_id else None,
        "car_interior_front": f"/uploads/cars/{driver.car_id}/interior_front.jpg" if hasattr(driver, "car_id") and driver.car_id else None,
        "car_interior_back": f"/uploads/cars/{driver.car_id}/interior_back.jpg" if hasattr(driver, "car_id") and driver.car_id else None,
    }
    
    return photo_paths

# API для фильтрации водителей
@app.get("/api/drivers/filter")
async def filter_drivers(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    date_filter: Optional[str] = None,
    page: int = Query(1, ge=1)
):
    try:
        items_per_page = 10
        
        # Базовый запрос
        query = db.query(models.Driver).join(models.Car, models.Driver.id == models.Car.driver_id, isouter=True)
        
        # Применяем фильтры
        if status:
            query = query.filter(models.Driver.status == status)
        
        if date_filter:
            if date_filter == 'today':
                start_date = datetime.now().date()
                query = query.filter(models.Driver.created_at >= start_date)
            elif date_filter == 'week':
                start_date = datetime.now().date() - timedelta(days=7)
                query = query.filter(models.Driver.created_at >= start_date)
            elif date_filter == 'month':
                start_date = datetime.now().date() - timedelta(days=30)
                query = query.filter(models.Driver.created_at >= start_date)
        
        # Подсчет общего количества водителей
        total_drivers = query.count()
        
        # Пагинация
        offset = (page - 1) * items_per_page
        drivers = query.offset(offset).limit(items_per_page).all()
        
        # Расчет общего количества страниц
        total_pages = (total_drivers + items_per_page - 1) // items_per_page
        
        # Преобразуем объекты Driver в словари
        drivers_data = []
        for driver in drivers:
            car_data = {
                "model": driver.car.model if driver.car else "",
                "make": driver.car.make if driver.car else "",
                "license_plate": driver.car.license_plate if driver.car else ""
            }
            
            drivers_data.append({
                "id": driver.id,
                "full_name": driver.full_name,
                "callsign": driver.callsign,
                "phone": driver.phone,
                "tariff": driver.tariff,
                "balance": driver.balance,
                "status": driver.status,
                "car": car_data
            })
        
        return {
            "drivers": drivers_data,
            "total_drivers": total_drivers,
            "page": page,
            "total_pages": total_pages
        }
    except Exception as e:
        return {"success": False, "detail": str(e)}

# API для поиска водителей
@app.get("/api/drivers/search")
async def search_drivers(
    query: str,
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1)
):
    try:
        if len(query) < 3:
            return {"success": False, "detail": "Минимальная длина поискового запроса - 3 символа"}
        
        items_per_page = 10
        search_term = f"%{query}%"
        
        # Поиск водителей
        search_query = db.query(models.Driver).join(
            models.Car, models.Driver.id == models.Car.driver_id, isouter=True
        ).filter(
            or_(
                models.Driver.full_name.ilike(search_term),
                models.Driver.callsign.ilike(search_term),
                models.Driver.phone.ilike(search_term),
                models.Car.license_plate.ilike(search_term)
            )
        )
        
        # Подсчет общего количества найденных водителей
        total_drivers = search_query.count()
        
        # Пагинация
        offset = (page - 1) * items_per_page
        drivers = search_query.offset(offset).limit(items_per_page).all()
        
        # Расчет общего количества страниц
        total_pages = (total_drivers + items_per_page - 1) // items_per_page
        
        # Преобразуем объекты Driver в словари
        drivers_data = []
        for driver in drivers:
            car_data = {
                "model": driver.car.model if driver.car else "",
                "make": driver.car.make if driver.car else "",
                "license_plate": driver.car.license_plate if driver.car else ""
            }
            
            drivers_data.append({
                "id": driver.id,
                "full_name": driver.full_name,
                "callsign": driver.callsign,
                "phone": driver.phone,
                "tariff": driver.tariff,
                "balance": driver.balance,
                "status": driver.status,
                "car": car_data
            })
        
        return {
            "success": True,
            "drivers": drivers_data,
            "total_drivers": total_drivers,
            "page": page,
            "total_pages": total_pages
        }
    except Exception as e:
        return {"success": False, "detail": str(e)}

# Добавляем маршруты для создания водителя
@app.get("/disp/create_driver", response_class=HTMLResponse)
async def disp_create_driver(request: Request, db: Session = Depends(get_db)):
    """Страница создания нового водителя (перенаправление на шаг 1)"""
    return RedirectResponse(url="/disp/create_driver_step1")

@app.get("/disp/create_driver_step1", response_class=HTMLResponse)
async def disp_create_driver_step1(request: Request, db: Session = Depends(get_db)):
    """Шаг 1: Персональные данные водителя"""
    # Получаем всех водителей из БД для статистики
    drivers = crud.get_drivers(db)
    
    # Расчет суммарного баланса всех водителей
    total_balance = sum(driver.balance for driver in drivers) if drivers else 0
    
    # Получаем количество свободных и занятых водителей
    available_drivers = len([d for d in drivers if getattr(d, 'is_busy', False) == False]) if drivers else 0
    busy_drivers = len(drivers) - available_drivers if drivers else 0
    
    current_year = datetime.now().year
    
    template_data = {
        "request": request,
        "current_page": "create_driver",
        "total_drivers": len(drivers) if drivers else 0,
        "available_drivers": available_drivers,
        "busy_drivers": busy_drivers,
        "total_balance": f"{total_balance:.0f}",
        "current_year": current_year
    }
    
    return templates.TemplateResponse("disp/create_driver_step1.html", template_data)

@app.get("/disp/create_driver_step2", response_class=HTMLResponse)
async def disp_create_driver_step2(request: Request, db: Session = Depends(get_db)):
    """Шаг 2: Информация об автомобиле"""
    # Получаем всех водителей из БД для статистики
    drivers = crud.get_drivers(db)
    
    # Расчет суммарного баланса всех водителей
    total_balance = sum(driver.balance for driver in drivers) if drivers else 0
    
    # Получаем количество свободных и занятых водителей
    available_drivers = len([d for d in drivers if getattr(d, 'is_busy', False) == False]) if drivers else 0
    busy_drivers = len(drivers) - available_drivers if drivers else 0
    
    current_year = datetime.now().year
    
    template_data = {
        "request": request,
        "current_page": "create_driver",
        "total_drivers": len(drivers) if drivers else 0,
        "available_drivers": available_drivers,
        "busy_drivers": busy_drivers,
        "total_balance": f"{total_balance:.0f}",
        "current_year": current_year
    }
    
    return templates.TemplateResponse("disp/create_driver_step2.html", template_data)

@app.get("/disp/create_driver_step3", response_class=HTMLResponse)
async def disp_create_driver_step3(request: Request, db: Session = Depends(get_db)):
    """Шаг 3: Фотографии автомобиля"""
    # Получаем всех водителей из БД для статистики
    drivers = crud.get_drivers(db)
    
    # Расчет суммарного баланса всех водителей
    total_balance = sum(driver.balance for driver in drivers) if drivers else 0
    
    # Получаем количество свободных и занятых водителей
    available_drivers = len([d for d in drivers if getattr(d, 'is_busy', False) == False]) if drivers else 0
    busy_drivers = len(drivers) - available_drivers if drivers else 0
    
    current_year = datetime.now().year
    
    template_data = {
        "request": request,
        "current_page": "create_driver",
        "total_drivers": len(drivers) if drivers else 0,
        "available_drivers": available_drivers,
        "busy_drivers": busy_drivers,
        "total_balance": f"{total_balance:.0f}",
        "current_year": current_year
    }
    
    return templates.TemplateResponse("disp/create_driver_step3.html", template_data)

# API для создания водителя
@app.post("/api/drivers/create")
async def create_driver(
    request: Request,
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    birth_date: str = Form(...),
    personal_number: str = Form(...),
    phone: str = Form(...),
    driver_license: str = Form(...),
    license_issue_date: Optional[str] = Form(None),
    license_expiry_date: Optional[str] = Form(None),
    address: Optional[str] = Form(None),
    passport_front: Optional[UploadFile] = File(default=None),
    passport_back: Optional[UploadFile] = File(default=None),
    license_front: Optional[UploadFile] = File(default=None),
    license_back: Optional[UploadFile] = File(default=None),
    car_make: str = Form(...),
    car_model: str = Form(...),
    car_color: str = Form(...),
    car_year: str = Form(...),
    transmission: str = Form(...),
    boosters: Optional[str] = Form("0"),
    child_seats: Optional[str] = Form("0"),
    autopark: Optional[str] = Form(None),
    city: Optional[str] = Form(None),
    is_park_car: Optional[bool] = Form(False),
    callsign: str = Form(...),
    license_plate: str = Form(...),
    vin: str = Form(...),
    body_number: Optional[str] = Form(None),
    registration: Optional[str] = Form(None),
    has_sticker: Optional[bool] = Form(False),
    has_lightbox: Optional[bool] = Form(False),
    tariff: str = Form(...),
    category: Optional[str] = Form(None),
    car_front: Optional[UploadFile] = File(default=None),
    car_back: Optional[UploadFile] = File(default=None),
    car_right: Optional[UploadFile] = File(default=None),
    car_left: Optional[UploadFile] = File(default=None),
    car_interior_front: Optional[UploadFile] = File(default=None),
    car_interior_back: Optional[UploadFile] = File(default=None),
    driver_with_license: Optional[UploadFile] = File(default=None)
):
    """API для создания нового водителя"""
    try:
        # Создаем папку для хранения файлов, если ее нет
        upload_dir = Path("uploads/drivers")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Генерируем уникальный ID для водителя
        driver_unique_id = personal_number  # Используем переданный персональный номер как уникальный ID
        driver_dir = upload_dir / driver_unique_id
        driver_dir.mkdir(exist_ok=True)
        
        # Сохраняем загруженные файлы
        async def save_file(file: UploadFile, filename: str):
            if file is None:
                return None
                
            contents = await file.read()
            file_path = driver_dir / filename
            with open(file_path, "wb") as f:
                f.write(contents)
            return str(file_path)
        
        # Сохраняем документы
        passport_front_path = await save_file(passport_front, f"passport_front.jpg") if passport_front else None
        passport_back_path = await save_file(passport_back, f"passport_back.jpg") if passport_back else None
        license_front_path = await save_file(license_front, f"license_front.jpg") if license_front else None
        license_back_path = await save_file(license_back, f"license_back.jpg") if license_back else None
        
        # Сохраняем фотографии автомобиля
        car_front_path = await save_file(car_front, f"car_front.jpg") if car_front else None
        car_back_path = await save_file(car_back, f"car_back.jpg") if car_back else None
        car_right_path = await save_file(car_right, f"car_right.jpg") if car_right else None
        car_left_path = await save_file(car_left, f"car_left.jpg") if car_left else None
        car_interior_front_path = await save_file(car_interior_front, f"car_interior_front.jpg") if car_interior_front else None
        car_interior_back_path = await save_file(car_interior_back, f"car_interior_back.jpg") if car_interior_back else None
        driver_with_license_path = await save_file(driver_with_license, f"driver_with_license.jpg") if driver_with_license else None
        
        # Преобразуем строковые даты в объекты date
        from datetime import datetime
        try:
            # Ожидаем формат DD.MM.YYYY
            birthdate = datetime.strptime(birth_date, "%d.%m.%Y").date() if birth_date else None
            license_issue = datetime.strptime(license_issue_date, "%d.%m.%Y").date() if license_issue_date else None
            license_expiry = datetime.strptime(license_expiry_date, "%d.%m.%Y").date() if license_expiry_date else None
        except ValueError as e:
            # Если формат неверный, попробуем другие распространенные форматы
            try:
                # Попробуем формат YYYY-MM-DD
                if birth_date:
                    birthdate = datetime.strptime(birth_date, "%Y-%m-%d").date()
                else:
                    birthdate = None
                
                if license_issue_date:
                    license_issue = datetime.strptime(license_issue_date, "%Y-%m-%d").date()
                else:
                    license_issue = None
                
                if license_expiry_date:
                    license_expiry = datetime.strptime(license_expiry_date, "%Y-%m-%d").date()
                else:
                    license_expiry = None
            except ValueError:
                # Если и это не сработало, устанавливаем дефолтные значения
                import traceback
                print(f"Ошибка при обработке дат: {traceback.format_exc()}")
                birthdate = datetime.now().date()
                license_issue = datetime.now().date()
                license_expiry = datetime.now().date()
        
        # Преобразуем строковые значения в числовые
        try:
            car_year_int = int(car_year) if car_year else 2000
        except (ValueError, TypeError):
            car_year_int = 2000
            
        try:
            boosters_int = int(boosters) if boosters else 0
        except (ValueError, TypeError):
            boosters_int = 0
            
        try:
            child_seats_int = int(child_seats) if child_seats else 0
        except (ValueError, TypeError):
            child_seats_int = 0
        
        # Создаем запись водителя в БД
        driver_data = {
            "full_name": full_name,
            "birthdate": birthdate,
            "callsign": callsign,
            "unique_id": driver_unique_id,
            "city": city or "Бишкек",  # Дефолтное значение
            "driver_license_number": driver_license,
            "balance": 0.0,
            "tariff": tariff,
            "taxi_park": autopark or "Ош Титан Парк"  # Дефолтное значение
        }
        
        # Добавляем дату выдачи прав только если она указана
        if license_issue:
            driver_data["driver_license_issue_date"] = license_issue
        
        # Создаем водителя через функцию из crud
        driver = crud.create_driver(db=db, driver=schemas.DriverCreate(**driver_data))
        
        # Создаем запись автомобиля в БД
        car_data = {
            "brand": car_make,
            "model": car_model,
            "year": car_year_int,
            "transmission": transmission,
            "has_booster": boosters_int > 0,
            "has_child_seat": child_seats_int > 0,
            "tariff": tariff,
            "license_plate": license_plate,
            "vin": vin,
            "service_type": category or "Такси",
            "photo_front": car_front_path,
            "photo_rear": car_back_path,
            "photo_right": car_right_path,
            "photo_left": car_left_path,
            "photo_interior_front": car_interior_front_path,
            "photo_interior_rear": car_interior_back_path
        }
        
        # Создаем автомобиль через функцию из crud
        car = crud.create_car(db=db, car=schemas.CarCreate(**car_data), driver_id=driver.id)
        
        return {"status": "success", "driver_id": driver.id}
    
    except Exception as e:
        db.rollback()
        import traceback
        trace = traceback.format_exc()
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e), "trace": trace}
        )

@app.post("/api/drivers/accept-all", response_class=JSONResponse)
async def accept_all_drivers(db: Session = Depends(get_db)):
    """API для принятия всех водителей"""
    try:
        # Получаем всех водителей из БД
        drivers = db.query(models.Driver).all()
        
        # Считаем количество обновленных водителей
        updated_count = 0
        
        # Обновляем статус всех водителей на 'accepted'
        for driver in drivers:
            if getattr(driver, 'status', 'pending') != 'accepted':
                driver.status = 'accepted'
                updated_count += 1
        
        # Сохраняем изменения в БД
        db.commit()
        
        return JSONResponse(
            status_code=200, 
            content={
                "success": True, 
                "detail": f"Успешно обновлено {updated_count} водителей", 
                "updated_count": updated_count
            }
        )
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500, 
            content={"success": False, "detail": str(e)}
        )

@app.get("/login", response_class=HTMLResponse)
async def get_login(request: Request):
    """Страница входа в систему"""
    return templates.TemplateResponse("disp/login.html", {"request": request})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    # Простая проверка логина и пароля (в реальном приложении нужно использовать хеширование и т.д.)
    if username == "admin" and password == "admin":
        response = RedirectResponse(url="/disp/", status_code=303)
        # Генерируем сессионный токен и устанавливаем куки
        session_token = secrets.token_hex(16)
        # Устанавливаем куки с сроком действия 1 день
        response.set_cookie(key="session", value=session_token, httponly=True, max_age=86400)
        return response
    else:
        return RedirectResponse(url="/login?error=1", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 