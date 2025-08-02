from fastapi import FastAPI, Depends, Request, Response, Query, Form, UploadFile, File, HTTPException, status, Cookie
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import os, sys, random, string, json, time, math, re, asyncio, logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator, ValidationError
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import jose.jwt
import secrets
import uuid
from pathlib import Path
from math import ceil

# Включить логирование SQL-запросов
import logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Импорт модулей проекта
from . import crud, models, schemas
from .database import engine, SessionLocal, get_db, Base
from .routers import drivers, cars, orders, messages
from .models import TokenResponse

# Выполняем миграцию базы данных
# from .migration import run_migrations
# run_migrations()

# Создаем все таблицы в базе данных
Base.metadata.create_all(bind=engine)

# Создаем директории для загрузки файлов
os.makedirs("uploads", exist_ok=True)
os.makedirs("uploads/cars", exist_ok=True)

# Создаем экземпляр FastAPI
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
        # Список исключенных путей, которые не требуют авторизации
        excluded_paths = ['/disp/login', '/login', '/static', '/driver/']
        
        # Проверяем, начинается ли путь с любого из исключенных путей
        is_excluded = any(request.url.path.startswith(path) for path in excluded_paths)
        
        # Если путь не исключен, проверяем наличие сессии
        if not is_excluded:
            session = request.cookies.get("session")
            if not session:
                return RedirectResponse(url="/disp/login", status_code=303)
        
        return await call_next(request)

app.add_middleware(AuthMiddleware)

# Модель для запроса пополнения баланса
class BalanceAddRequest(BaseModel):
    driver_id: int
    amount: int

# Константы для JWT
SECRET_KEY = "wazir_secret_key_change_in_production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней

# Модель запроса для входа водителя
class DriverLoginRequest(BaseModel):
    phone: str

# Модель запроса для подтверждения кода
class VerifyCodeRequest(BaseModel):
    phone: str
    code: str

# Модель запроса для обновления профиля
class UpdateProfileRequest(BaseModel):
    first_name: str
    last_name: str
    phone: Optional[str] = None
    user_id: Optional[int] = None

# Функция для создания JWT токена
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jose.jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@app.get("/driver/", response_class=HTMLResponse)
async def driver_main(request: Request):
    return RedirectResponse(url="/driver/auth/step1")

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
async def verify_driver(driver_id: int, request: Request, db: Session = Depends(get_db)):
    """API для верификации водителя (принять/отклонить)"""
    try:
        # Получаем данные запроса
        data = await request.json()
        status = data.get("status")
        if not status:
            return JSONResponse(status_code=400, content={"success": False, "detail": "Статус не указан"})
        
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return JSONResponse(status_code=404, content={"success": False, "detail": "Водитель не найден"})
        
        # Обновляем статус верификации
        if status in ["accepted", "rejected"]:
            driver.status = status
            
            # Получаем или создаем общую запись верификации для фотоконтроля
            verification = db.query(models.DriverVerification).filter(
                models.DriverVerification.driver_id == driver_id,
                models.DriverVerification.verification_type == "photo_control"
            ).first()
            
            if verification:
                # Обновляем статус общей верификации
                verification.status = status
                verification.verified_at = datetime.now()
                if status == "rejected":
                    verification.comment = "Фотографии отклонены"
                else:
                    verification.comment = "Фотографии приняты"
            else:
                # Создаем новую запись верификации
                verification = models.DriverVerification(
                    driver_id=driver_id,
                    status=status,
                    verification_type="photo_control",
                    comment=f"Фотографии {status}",
                    created_at=datetime.now(),
                    verified_at=datetime.now()
                )
                db.add(verification)
            
            # Сохраняем изменения
            db.commit()
            return {"success": True}
        else:
            return JSONResponse(status_code=400, content={"success": False, "detail": "Недопустимый статус"})
    except Exception as e:
        import traceback
        print(f"Ошибка при верификации водителя: {str(e)}")
        print(traceback.format_exc())
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
        
        # Безопасно получаем значение is_mobile_registered с защитой от отсутствия колонки
        is_mobile_registered = False
        try:
            if hasattr(driver, "is_mobile_registered"):
                is_mobile_registered = driver.is_mobile_registered
        except:
            # Если колонка недоступна, используем логику по умолчанию
            is_mobile_registered = False
            
        # Определяем источник создания водителя
        # Если колонка недоступна или значение False, используем старую логику
        if not is_mobile_registered:
            # Старая логика: Если у водителя отсутствуют фотографии, считаем что он создан в диспетчерской
            is_disp_created = not any([
                getattr(driver, "passport_front_path", None), 
                getattr(driver, "passport_back_path", None),
                getattr(driver, "license_front_path", None),
                getattr(driver, "license_back_path", None)
            ])
        else:
            # Новая логика: Используем явный флаг
            is_disp_created = not is_mobile_registered
        
        # Форматируем дату регистрации
        registration_date = None
        try:
            if hasattr(driver, "registration_date") and driver.registration_date:
                registration_date = driver.registration_date.strftime("%d.%m.%Y")
        except:
            # Если колонка недоступна, дата останется None
            pass
        
        # Форматируем дату выдачи водительского удостоверения
        license_date = ""
        try:
            if hasattr(driver, "driver_license_issue_date") and driver.driver_license_issue_date:
                license_date = driver.driver_license_issue_date.strftime("%d.%m.%Y")
        except:
            # В случае ошибки, используем строковое представление
            if hasattr(driver, "driver_license_issue_date"):
                license_date = str(driver.driver_license_issue_date)
        
        # Собираем детальную информацию
        driver_data = {
            "id": driver.id,
            "full_name": driver.full_name,
            "callsign": getattr(driver, "callsign", ""),
            "phone": getattr(driver, "phone", ""),
            "city": getattr(driver, "city", ""),
            "birthdate": str(driver.birth_date) if hasattr(driver, "birth_date") else "",
            "driver_license": getattr(driver, "driver_license_number", ""),
            "driver_license_issue_date": license_date,
            "balance": getattr(driver, "balance", 0),
            "tariff": getattr(driver, "tariff", ""),
            "taxi_park": getattr(driver, "taxi_park", ""),
            "status": getattr(driver, "status", "pending"),
            "photos": photo_paths,
            "is_disp_created": is_disp_created
        }
        
        # Добавляем дату регистрации, если она доступна
        if registration_date:
            driver_data["registration_date"] = registration_date
        
        # Если есть автомобиль, добавляем его данные
        if car:
            car_data = {
                "id": car.id,
                "brand": getattr(car, "brand", ""),
                "model": getattr(car, "model", ""),
                "year": getattr(car, "year", 0),
                "color": getattr(car, "color", ""),
                "transmission": getattr(car, "transmission", ""),
                "license_plate": getattr(car, "license_plate", ""),
                "vin": getattr(car, "vin", ""),
                "has_booster": getattr(car, "has_booster", False),
                "has_child_seat": getattr(car, "has_child_seat", False),
                "tariff": getattr(car, "tariff", ""),
                "service_type": getattr(car, "service_type", "")
            }
            driver_data["car"] = car_data
        
        return driver_data
    except Exception as e:
        import traceback
        print(f"Ошибка при получении данных водителя: {str(e)}")
        print(traceback.format_exc())
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
    page: int = Query(1, ge=1),
    photo_control: Optional[bool] = False
):
    """API для фильтрации водителей с опцией фотоконтроля"""
    try:
        page_size = 10
        offset = (page - 1) * page_size
        
        # Базовый запрос
        query = db.query(models.Driver)
        
        # Фильтрация по статусу
        if status:
            query = query.filter(models.Driver.status == status)
        
        # Фильтрация по дате
        if date_filter:
            today = datetime.now().date()
            
            if date_filter == "today":
                query = query.filter(func.date(models.Driver.registration_date) == today)
            elif date_filter == "week":
                week_ago = today - timedelta(days=7)
                query = query.filter(models.Driver.registration_date >= week_ago)
            elif date_filter == "month":
                month_ago = today - timedelta(days=30)
                query = query.filter(models.Driver.registration_date >= month_ago)
        
        # Если нужны водители для фотоконтроля
        photo_control_drivers = []
        if photo_control:
            # Фильтруем тех, у кого есть загруженные фотографии, но нет верификации
            drivers_with_photos = query.all()
            
            for driver in drivers_with_photos:
                # Проверяем наличие фотографий
                has_photos = False
                passport_front = getattr(driver, "passport_front_path", None)
                passport_back = getattr(driver, "passport_back_path", None)
                license_front = getattr(driver, "license_front_path", None)
                license_back = getattr(driver, "license_back_path", None)
                
                if passport_front or passport_back or license_front or license_back:
                    has_photos = True
                
                if not has_photos:
                    car = db.query(models.Car).filter(models.Car.driver_id == driver.id).first()
                    if car and (car.photo_front or car.photo_rear or car.photo_right or 
                               car.photo_left or car.photo_interior_front or car.photo_interior_rear):
                        has_photos = True
                
                # Проверяем статус верификации
                if has_photos:
                    verifications = db.query(models.DriverVerification).filter(
                        models.DriverVerification.driver_id == driver.id,
                        models.DriverVerification.verification_type.like("photo_%")
                    ).all()
                    
                    # Добавляем статусы верификации к данным водителя
                    driver_dict = {
                        "id": driver.id,
                        "full_name": driver.full_name,
                        "callsign": getattr(driver, "callsign", ""),
                        "phone": getattr(driver, "phone", ""),
                        "city": getattr(driver, "city", ""),
                        "status": getattr(driver, "status", ""),
                        "registration_date": getattr(driver, "registration_date", None)
                    }
                    
                    if driver.registration_date:
                        driver_dict["registration_date"] = driver.registration_date.strftime("%d.%m.%Y")
                    
                    # Если это водитель без верификации или с pending верификацией, добавляем его
                    if not verifications or any(v.status == "pending" for v in verifications):
                        driver_dict["photo_status"] = {v.verification_type.replace("photo_", ""): v.status for v in verifications}
                        photo_control_drivers.append(driver_dict)
            
            # Считаем количество водителей по статусам
            all_verifications = db.query(models.DriverVerification).filter(
                models.DriverVerification.verification_type.like("photo_%")
            ).all()
            
            pending_count = len([v for v in all_verifications if v.status == "pending"])
            accepted_count = len([v for v in all_verifications if v.status == "accepted"])
            rejected_count = len([v for v in all_verifications if v.status == "rejected"])
            
            # Вычисляем общий баланс
            total_balance = db.query(func.sum(models.Driver.balance)).scalar() or 0
            
            return {
                "drivers": photo_control_drivers,
                "total": len(photo_control_drivers),
                "pending_count": pending_count,
                "accepted_count": accepted_count,
                "rejected_count": rejected_count,
                "total_balance": f"{total_balance:.0f}"
            }
        
        # Обычная фильтрация
        total = query.count()
        drivers = query.offset(offset).limit(page_size).all()
        
        driver_list = []
        for driver in drivers:
            driver_dict = {
                "id": driver.id,
                "full_name": driver.full_name,
                "callsign": getattr(driver, "callsign", ""),
                "phone": getattr(driver, "phone", ""),
                "city": getattr(driver, "city", ""),
                "status": getattr(driver, "status", "")
            }
            
            if hasattr(driver, "registration_date") and driver.registration_date:
                driver_dict["registration_date"] = driver.registration_date.strftime("%d.%m.%Y")
            
            driver_list.append(driver_dict)
        
        return {
            "drivers": driver_list,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": ceil(total / page_size)
        }
    except Exception as e:
        import traceback
        print(f"Ошибка при фильтрации водителей: {str(e)}")
        print(traceback.format_exc())
        return JSONResponse(
            status_code=500, 
            content={"detail": f"Ошибка сервера: {str(e)}"}
        )

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
    driver_with_license: Optional[UploadFile] = File(default=None),
    sts: Optional[str] = Form("12 КG 123456")  # Добавляем новый параметр с дефолтным значением
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
        
        # Устанавливаем значение даты рождения
        birthdate = None
        try:
            # Ожидаем формат DD.MM.YYYY
            birthdate = datetime.strptime(birth_date, "%d.%m.%Y").date() if birth_date else None
            print(f"Преобразована дата рождения: {birthdate}")
        except ValueError:
            try:
                # Пробуем альтернативный формат YYYY-MM-DD
                birthdate = datetime.strptime(birth_date, "%Y-%m-%d").date() if birth_date else None
                print(f"Преобразована дата рождения (альт. формат): {birthdate}")
            except ValueError:
                print(f"Не удалось преобразовать дату рождения: {birth_date}")
                # Если не удалось преобразовать, используем текущую дату
                birthdate = datetime.now().date()
        
        # Устанавливаем значение даты выдачи водительского удостоверения
        license_issue = None
        try:
            # Ожидаем формат DD.MM.YYYY
            license_issue = datetime.strptime(license_issue_date, "%d.%m.%Y").date() if license_issue_date else None
            print(f"Преобразована дата выдачи ВУ: {license_issue}")
        except ValueError:
            try:
                # Пробуем альтернативный формат YYYY-MM-DD
                license_issue = datetime.strptime(license_issue_date, "%Y-%m-%d").date() if license_issue_date else None
                print(f"Преобразована дата выдачи ВУ (альт. формат): {license_issue}")
            except ValueError:
                print(f"Не удалось преобразовать дату выдачи ВУ: {license_issue_date}")
                # Если не удалось преобразовать и дата указана, то используем строку
                if license_issue_date:
                    license_issue = license_issue_date
        
        # Устанавливаем значение даты окончания действия водительского удостоверения
        license_expiry = None
        try:
            # Ожидаем формат DD.MM.YYYY
            license_expiry = datetime.strptime(license_expiry_date, "%d.%m.%Y").date() if license_expiry_date else None
        except ValueError:
            try:
                # Пробуем альтернативный формат YYYY-MM-DD
                license_expiry = datetime.strptime(license_expiry_date, "%Y-%m-%d").date() if license_expiry_date else None
            except ValueError:
                print(f"Не удалось преобразовать дату окончания ВУ: {license_expiry_date}")
        
        # Преобразуем год автомобиля в целое число
        car_year_int = int(car_year) if car_year and car_year.isdigit() else 2020
        
        # Преобразуем количество бустеров и детских кресел в целые числа
        boosters_int = int(boosters) if boosters and boosters.isdigit() else 0
        child_seats_int = int(child_seats) if child_seats and child_seats.isdigit() else 0
        
        # Создаем папку для хранения фотографий водителя
        driver_photos_dir = os.path.join("fast/static/uploads/drivers", personal_number)
        os.makedirs(driver_photos_dir, exist_ok=True)
        
        # Создаем запись водителя в БД
        driver_data = {
            "full_name": full_name,
            "unique_id": phone.replace('+', '').ljust(20, '0')[:20],  # Гарантируем ровно 20 символов
            "phone": phone,  # Добавляем телефон
            "city": city or "Бишкек",  # Дефолтное значение
            "driver_license_number": driver_license,
            "balance": 0.0,
            "tariff": tariff,
            "taxi_park": autopark or "Ош Титан Парк",  # Дефолтное значение
            "callsign": phone.replace('+', '')  # Используем номер телефона как позывной
        }
        
        # Добавляем дату рождения если она указана
        if birthdate:
            driver_data["birth_date"] = birthdate
        else:
            driver_data["birth_date"] = datetime.now().date()  # Устанавливаем текущую дату как значение по умолчанию
        
        # Добавляем дату выдачи прав только если она указана
        if license_issue:
            driver_data["driver_license_issue_date"] = license_issue
            print(f"Добавлена дата выдачи прав: {license_issue}")
        
        # Выводим данные для отладки
        print(f"Данные водителя для сохранения: {driver_data}")
        
        # Создаем водителя через функцию из crud
        driver = crud.create_driver(db=db, driver=schemas.DriverCreate(**driver_data))
        
        # Создаем запись автомобиля в БД
        car_data = {
            "brand": car_make,
            "model": car_model,
            "color": car_color,
            "year": car_year_int,
            "transmission": transmission,
            "has_booster": boosters_int > 0,
            "has_child_seat": child_seats_int > 0,
            "tariff": tariff,
            "license_plate": license_plate,
            "vin": vin,
            "service_type": category or "Такси",
            "sts": sts,  # Добавляем СТС
            "photo_front": car_front_path,
            "photo_rear": car_back_path,
            "photo_right": car_right_path,
            "photo_left": car_left_path,
            "photo_interior_front": car_interior_front_path,
            "photo_interior_rear": car_interior_back_path
        }
        
        # Создаем автомобиль через функцию из crud
        car = crud.create_car(db=db, car=schemas.CarCreate(**car_data), driver_id=driver.id)
        
        # Добавляем документы водителя
        driver_documents = models.DriverDocuments(
            driver_id=driver.id,
            passport_front=passport_front_path,
            passport_back=passport_back_path,
            license_front=license_front_path,
            license_back=license_back_path,
            driver_with_license=driver_with_license_path,
            is_verified=False
        )
        db.add(driver_documents)
        db.commit()
        db.refresh(driver_documents)
        
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

@app.delete("/api/drivers/{driver_id}", response_class=JSONResponse)
async def api_delete_driver(driver_id: int, db: Session = Depends(get_db)):
    """API для удаления водителя"""
    try:
        # Получаем водителя по ID
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return JSONResponse(
                status_code=404, 
                content={"success": False, "detail": "Водитель не найден"}
            )
        
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
            print(f"Удалено документов: {len(documents)}")
        except Exception as e:
            print(f"Ошибка при удалении driver_documents: {str(e)}")
            
        # Удаляем записи в таблице driver_verifications
        try:
            verifications = db.query(models.DriverVerification).filter(models.DriverVerification.driver_id == driver_id).all()
            for verification in verifications:
                db.delete(verification)
            print(f"Удалено верификаций: {len(verifications)}")
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
            cars = db.query(models.Car).filter(models.Car.driver_id == driver_id).all()
            for car in cars:
                db.delete(car)
        except Exception as e:
            print(f"Ошибка при удалении cars: {str(e)}")
        
        # Проверяем наличие и удаляем записи в таблице DriverCar
        try:
            # Безопасный способ проверить существование класса модели
            if hasattr(models, 'DriverCar'):
                driver_cars = db.query(models.DriverCar).filter(models.DriverCar.driver_id == driver_id).all()
                for car in driver_cars:
                    db.delete(car)
            else:
                print("Модель DriverCar не найдена в models.py")
                
                # Альтернативный подход - прямой запрос к таблице
                try:
                    db.execute(f"DELETE FROM driver_cars WHERE driver_id = {driver_id}")
                except Exception as e:
                    print(f"Ошибка при выполнении SQL запроса к driver_cars: {str(e)}")
        except Exception as e:
            print(f"Ошибка при удалении driver_cars: {str(e)}")
        
        # Удаляем водителя
        db.delete(driver)
        db.commit()
        
        return JSONResponse(
            status_code=200,
            content={"success": True, "detail": "Водитель успешно удален"}
        )
    except Exception as e:
        db.rollback()
        error_detail = f"Ошибка при удалении водителя: {str(e)}"
        print(error_detail)
        return JSONResponse(
            status_code=500,
            content={"success": False, "detail": error_detail}
        )

@app.get("/login", response_class=HTMLResponse)
async def get_login_redirect(request: Request):
    """Перенаправление со старого пути на новый"""
    return RedirectResponse(url="/disp/login", status_code=303)

@app.post("/login")
async def login_redirect(
    request: Request,
    username: str = Form(...),
    password: str = Form(...)
):
    """Перенаправление POST запросов со старого пути на новый"""
    response = RedirectResponse(url="/disp/login", status_code=303)
    return response

@app.get("/disp/login", response_class=HTMLResponse)
async def get_login(request: Request):
    """Страница входа в систему"""
    return templates.TemplateResponse("disp/login.html", {"request": request})

@app.post("/disp/login")
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
        return RedirectResponse(url="/disp/login?error=1", status_code=303)

# Добавляем API роутеры для водительского приложения
@app.post("/api/driver/login", response_model=dict)
async def driver_login(request: DriverLoginRequest, db: Session = Depends(get_db)):
    """Отправка кода подтверждения на телефон водителя"""
    # Форматируем номер телефона - удаляем все кроме цифр
    phone = ''.join(filter(str.isdigit, request.phone))
    
    # Проверяем, существует ли уже пользователь с таким номером
    user = crud.get_driver_user_by_phone(db, phone)
    
    # Если пользователя нет, создаем его
    if not user:
        user = crud.create_driver_user(db, schemas.DriverUserCreate(phone=phone))
    
    # В реальном приложении здесь была бы отправка SMS
    # Для тестирования используем фиксированный код 1111
    verification_code = "1111"
    
    # В реальном приложении код нужно сохранить в кеше или БД
    # и связать с номером телефона для последующей проверки
    
    return {"success": True, "message": "Код подтверждения отправлен"}


@app.post("/api/driver/verify-code", response_model=TokenResponse)
async def verify_code(request: VerifyCodeRequest, response: Response = None, db: Session = Depends(get_db)):
    """
    Проверка кода подтверждения и выдача JWT токена.
    
    Возвращает:
    - access_token: JWT токен для аутентификации
    - token_type: Тип токена (bearer)
    - user_id: ID пользователя
    - has_driver: Флаг, указывающий, заполнил ли пользователь анкету водителя
    - driver_id: ID водителя (если анкета заполнена, иначе null)
    """
    # Форматируем номер телефона - удаляем все кроме цифр
    raw_phone = request.phone
    phone = ''.join(filter(str.isdigit, request.phone))
    print(f"Верификация кода для телефона: {phone} (исходный: {raw_phone})")
    
    # Получаем пользователя по номеру телефона
    user = crud.get_driver_user_by_phone(db, phone)
    if not user:
        print(f"Пользователь с телефоном {phone} не найден")
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    print(f"Найден пользователь: id={user.id}, first_name={user.first_name}, driver_id={user.driver_id}")
    
    # В тестовом режиме проверяем только на фиксированный код 1111
    if request.code != "1111":
        print(f"Неверный код: {request.code}, ожидается 1111")
        raise HTTPException(status_code=400, detail="Неверный код подтверждения")
    
    # Отмечаем пользователя как верифицированного
    user_update = schemas.DriverUserUpdate(is_verified=True)
    user = crud.update_driver_user(db, user.id, user_update)
    
    # Обновляем время последнего входа
    crud.update_last_login(db, user.id)
    
    # Проверяем, связан ли пользователь с водителем (заполнена ли анкета)
    has_driver = user.driver_id is not None
    driver_id = user.driver_id
    print(f"Проверка наличия водителя через driver_id: driver_id={driver_id}, has_driver={has_driver}")
    
    # Расширенный поиск водителя по номеру телефона с разными форматами
    if not has_driver:
        print("Попытка найти водителя с различными форматами телефона")
        
        # Возможные форматы телефона
        phone_formats = [
            phone,                          # Без +
            '+' + phone,                    # С +
            '996' + phone[3:] if phone.startswith('996') else phone,  # Без 996 в начале
            phone.replace('-', ''),         # Без дефисов
            phone.replace(' ', '')          # Без пробелов
        ]
        
        # Попробуем разные форматы телефона
        for phone_format in phone_formats:
            print(f"Поиск водителя с телефоном {phone_format}")
            driver = db.query(models.Driver).filter(models.Driver.phone == phone_format).first()
            
            if driver:
                print(f"Найден водитель по номеру телефона {phone_format}: id={driver.id}, name={driver.full_name}")
                user.driver_id = driver.id
                db.commit()
                
                has_driver = True
                driver_id = driver.id
                print(f"Связали пользователя с водителем: user_id={user.id}, driver_id={driver_id}")
                break
            
        if not has_driver:
            print(f"Водитель с телефоном {phone} и похожими форматами не найден")
    else:
        # Получаем водителя, если он есть через driver_id
        driver = crud.get_driver(db, driver_id)
        has_driver = driver is not None  # Дополнительная проверка существования водителя
        print(f"Получен водитель через driver_id: id={driver.id if driver else None}")
    
    # Создаем JWT токен
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.id, "phone": phone},
        expires_delta=access_token_expires
    )
    
    # Устанавливаем куки с JWT токеном
    if response:
        print("Устанавливаем токен в куки")
        response.set_cookie(
            key="token",
            value=access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            samesite="strict"
        )
    else:
        print("Объект response не предоставлен, куки не будут установлены")
    
    # Формируем ответ
    response_data = {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "has_driver": has_driver,
        "driver_id": driver_id if has_driver else None
    }
    print(f"Отправляем ответ: {response_data}")
    return response_data

@app.post("/api/driver/update-profile")
async def update_profile(request: UpdateProfileRequest, db: Session = Depends(get_db)):
    """Обновление имени и фамилии пользователя"""
    # Определяем ID пользователя из запроса или из токена
    user_id = request.user_id
    
    if not user_id:
        # В реальном приложении здесь должна быть проверка токена
        raise HTTPException(status_code=401, detail="Требуется аутентификация")
    
    user = crud.get_driver_user(db, user_id)
    if not user:
        # Если пользователь не найден, но есть номер телефона, пробуем найти по нему
        if request.phone:
            user = crud.get_driver_user_by_phone(db, request.phone)
            if not user:
                raise HTTPException(status_code=404, detail="Пользователь не найден")
        else:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Обновляем данные пользователя
    user_update = schemas.DriverUserUpdate(
        first_name=request.first_name,
        last_name=request.last_name
    )
    user = crud.update_driver_user(db, user.id, user_update)
    
    return {"success": True, "message": "Профиль обновлен успешно"}

# Маршруты для интерфейса водителя (должны быть выше маршрута /)
@app.get("/driver/", response_class=HTMLResponse)
async def driver_main(request: Request):
    """Главная страница для водителей - перенаправление на авторизацию"""
    return RedirectResponse(url="/driver/auth/step1")

@app.get("/driver/auth/step1", response_class=HTMLResponse)
async def driver_auth_step1(request: Request):
    """Страница ввода номера телефона для водителя"""
    return templates.TemplateResponse("driver/auth/1.html", {"request": request})

@app.get("/driver/auth/step2", response_class=HTMLResponse)
async def driver_auth_step2(request: Request, phone: Optional[str] = None):
    """Страница ввода кода из СМС для водителя"""
    return templates.TemplateResponse("driver/auth/2.html", {"request": request, "phone": phone})

@app.get("/driver/auth/step3", response_class=HTMLResponse)
async def driver_auth_step3(request: Request):
    """Страница ввода имени и фамилии для водителя"""
    return templates.TemplateResponse("driver/auth/3.html", {"request": request})

@app.get("/driver/survey/1", response_class=HTMLResponse)
async def driver_survey_step1(request: Request):
    """Начальная страница анкеты для водителя"""
    return templates.TemplateResponse("driver/survey/1.html", {"request": request})

@app.get("/driver/survey/2", response_class=HTMLResponse)
async def driver_survey_step2(request: Request):
    """Вторая страница анкеты для водителя"""
    return templates.TemplateResponse("driver/survey/2.html", {"request": request})

@app.get("/driver/survey/3", response_class=HTMLResponse)
async def driver_survey_step3(request: Request):
    """Третья страница анкеты для водителя"""
    return templates.TemplateResponse("driver/survey/3.html", {"request": request})

@app.get("/driver/survey/4", response_class=HTMLResponse)
async def driver_survey_step4(request: Request):
    """Четвертая страница анкеты для водителя"""
    return templates.TemplateResponse("driver/survey/4.html", {"request": request})

@app.get("/driver/survey/5", response_class=HTMLResponse)
async def driver_survey_step5(request: Request):
    """Пятая страница анкеты для водителя"""
    return templates.TemplateResponse("driver/survey/5.html", {"request": request})

@app.get("/driver/survey/6", response_class=HTMLResponse)
async def driver_survey_step6(request: Request):
    """Шестая страница анкеты для водителя - выбор парка"""
    return templates.TemplateResponse("driver/survey/6.html", {"request": request})

@app.get("/driver/survey/7", response_class=HTMLResponse)
async def driver_survey_step7(request: Request):
    """Седьмая страница анкеты для водителя - информация о парке"""
    return templates.TemplateResponse("driver/survey/7.html", {"request": request})

@app.get("/driver/survey/7_1", response_class=HTMLResponse)
async def driver_survey_step7_1(request: Request):
    """Страница с условиями вывода средств в выбранном парке"""
    return templates.TemplateResponse("driver/survey/7_1.html", {"request": request})

@app.get("/driver/survey/8", response_class=HTMLResponse)
async def driver_survey_step8(request: Request):
    """Страница подтверждения данных анкеты"""
    return templates.TemplateResponse("driver/survey/8.html", {"request": request})

@app.get("/driver/survey/9", response_class=HTMLResponse)
async def driver_survey_step9(request: Request):
    """Страница с банковскими реквизитами для водителя"""
    return templates.TemplateResponse("driver/survey/9.html", {"request": request})

@app.get("/driver/survey/10", response_class=HTMLResponse)
async def driver_survey_step10(request: Request):
    """Страница с завершением анкеты для водителя"""
    return templates.TemplateResponse("driver/survey/10.html", {"request": request})

@app.get("/driver/profile", response_class=HTMLResponse)
async def driver_profile(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница профиля водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        print(f"Декодирование токена: {token[:20]}...")
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        print(f"Токен декодирован, user_id={user_id}")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            print(f"Пользователь с id={user_id} не найден, перенаправление на страницу авторизации")
            return RedirectResponse(url="/driver/auth/step1")
        
        print(f"Найден пользователь: id={user.id}, first_name={user.first_name}, driver_id={user.driver_id}")
        
        # Получаем данные водителя
        driver = None
        if user.driver_id:
            driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
            print(f"Найден водитель: id={driver.id if driver else 'None'}, name={driver.full_name if driver else 'None'}")
        
        if not driver:
            # Если водитель не найден или не привязан к пользователю, 
            # перенаправляем на страницу регистрации
            print("Водитель не найден, перенаправление на анкету")
            return RedirectResponse(url="/driver/survey/1")
        
        # Обновляем время последнего входа
        user.last_login = datetime.now()
        db.commit()
        
        # Получаем текущую дату
        current_date = datetime.now()
        
        car_info = ""
        if driver.cars and len(driver.cars) > 0:
            car = driver.cars[0]
            car_info = f"{car.brand} {car.model}, {car.license_plate}"
        
        # Счетчик проблем - подсчитываем количество проблем, которые отображаются на странице диагностики
        issues_count = 0
        
        # 1. Проверка наличия тарифа
        has_tariff = driver.tariff is not None and driver.tariff.strip() != ""
        if not has_tariff:
            issues_count += 1
        
        # 2. и 3. Проверка фотоконтроля
        # Получаем фотографии документов
        photos = await get_driver_photos(driver.id, db)
        
        # Проверка фотоконтроля через верификацию
        photo_verification = db.query(models.DriverVerification).filter(
            models.DriverVerification.driver_id == driver.id,
            models.DriverVerification.verification_type == "photo_control",
            models.DriverVerification.status == "accepted"
        ).first()
        
        car = driver.car
        # Если есть верификация со статусом accepted, значит фотоконтроль пройден
        sts_photo_passed = photo_verification is not None
        
        # Если нет верификации со статусом accepted, проверяем наличие СТС у автомобиля
        if not sts_photo_passed:
            sts_photo_passed = car is not None and hasattr(car, "sts") and car.sts is not None
            
        # Проверка фотоконтроля ВУ через ту же запись в DriverVerification
        license_photo_passed = photo_verification is not None
        
        # Если нет верификации со статусом accepted, проверяем наличие фотографий водительского удостоверения
        if not license_photo_passed:
            license_photo_passed = photos.get("license_front") is not None and photos.get("license_back") is not None
        
        if not sts_photo_passed:
            issues_count += 1
        
        if not license_photo_passed:
            issues_count += 1
        
        # 4. Проверка баланса
        min_balance = 10
        balance = driver.balance or 0
        
        if balance < min_balance:
            issues_count += 1
        
        # 5. Проверка наличия других ограничений
        has_limitations = False  # Здесь должна быть логика проверки других ограничений
        if has_limitations:
            issues_count += 1
        
        template_data = {
            "request": request,
            "user": user,
            "driver": driver,
            "driver_id": str(driver.id),
            "current_date": current_date,
            "tariff": driver.tariff,
            "driver_name": f"{user.first_name} {user.last_name}",
            "car_info": car_info,
            "issues_count": issues_count  # Передаем количество проблем в шаблон
        }
        
        print(f"Отрисовка профиля для водителя id={driver.id}")
        return templates.TemplateResponse("driver/profile/1.html", template_data)
    except jose.jwt.JWTError as e:
        # Если токен недействителен, перенаправляем на страницу авторизации
        print(f"Ошибка проверки JWT: {str(e)}")
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке профиля: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.post("/api/driver/complete-registration")
async def complete_driver_registration(request: Request, db: Session = Depends(get_db)):
    try:
        # Импортируем datetime в начале функции для использования во всех блоках
        from datetime import datetime, date
        
        # Получаем данные из запроса
        data = await request.json()
        print(f"Получены данные для регистрации водителя: {data}")
        
        # Проверяем наличие id пользователя (может быть в поле user_id или driver_id)
        user_id = data.get('user_id') or data.get('driver_id')
        if not user_id:
            print("❌ Ошибка: Не указан ID пользователя!")
            return {"status": "error", "message": "Не указан ID пользователя"}
        
        print(f"✅ Найден ID пользователя: {user_id}")
        
        # Получаем пользователя по ID
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            print(f"❌ Ошибка: Пользователь с ID {user_id} не найден!")
            return {"status": "error", "message": "Пользователь не найден"}
        
        # Проверяем, существует ли уже водитель для этого пользователя
        existing_driver = None
        if user.driver_id:
            existing_driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
            print(f"Найден связанный водитель: {existing_driver.id if existing_driver else None}")
        
        # Если не указано полное имя, возвращаем ошибку
        if not data.get('driver_name') and not data.get('driver_first_name'):
            print("❌ Ошибка: Не указано имя водителя!")
            return {"status": "error", "message": "Не указано имя водителя"}
        
        # Создаем или получаем полное имя
        if data.get('driver_name'):
            if data.get('driver_surname'):
                full_name = f"{data.get('driver_name')} {data.get('driver_surname')}"
            else:
                full_name = data.get('driver_name')
        else:
            if data.get('driver_last_name'):
                full_name = f"{data.get('driver_first_name')} {data.get('driver_last_name')}"
            else:
                full_name = data.get('driver_first_name')
                
        print(f"✅ Сформировано полное имя: {full_name}")
        
        # Генерируем уникальный ID
        unique_id = ""
        if data.get('driver_license_number'):
            # Используем номер водительского удостоверения
            unique_id = data.get('driver_license_number').replace(' ', '').ljust(20, '0')[:20]
        else:
            # Используем номер телефона, если есть
            unique_id = user.phone.replace('+', '').ljust(20, '0')[:20]
        
        print(f"Сгенерирован unique_id: {unique_id}")
        
        # Подготавливаем данные водителя
        driver_data = {
            "full_name": full_name,
            "unique_id": unique_id,
            "phone": user.phone,
            "city": data.get('driver_city', {}).get('name', 'Бишкек') if isinstance(data.get('driver_city'), dict) else data.get('driver_city', 'Бишкек'),
            "driver_license_number": data.get('driver_license_number', ''),
            "balance": 0.0,
            "tariff": data.get('driver_car_category', 'comfort'),
            "taxi_park": data.get('driver_car_park', 'Ош Титан Парк'),
            "callsign": user.phone.replace('+', ''),
            "address": data.get('driver_residential_address', '')
        }
        
        # Безопасно добавляем новые поля, если они поддерживаются моделью
        try:
            # Проверяем, поддерживает ли модель Driver новые поля
            if hasattr(models.Driver, "is_mobile_registered"):
                driver_data["is_mobile_registered"] = True
                print("Добавлено поле is_mobile_registered = True")
            
            if hasattr(models.Driver, "registration_date"):
                # Используем переменную datetime из импорта в начале функции
                driver_data["registration_date"] = datetime.now()
                print(f"Добавлено поле registration_date = {datetime.now()}")
        except Exception as e:
            print(f"Предупреждение: Не удалось установить новые поля: {str(e)}")
        
        # Устанавливаем дату рождения, если она указана
        if data.get('driver_birth_date'):
            try:
                from datetime import datetime
                birthdate = datetime.strptime(data['driver_birth_date'], "%d.%m.%Y").date()
                driver_data["birth_date"] = birthdate
                print(f"✅ Установлена дата рождения: {birthdate}")
            except ValueError as e:
                print(f"⚠️ Ошибка при преобразовании даты рождения {data['driver_birth_date']}: {str(e)}")
                try:
                    # Пробуем альтернативный формат
                    birthdate = datetime.strptime(data['driver_birth_date'], "%Y-%m-%d").date()
                    driver_data["birth_date"] = birthdate
                    print(f"✅ Установлена дата рождения (альт. формат): {birthdate}")
                except ValueError as e:
                    print(f"❌ Не удалось преобразовать дату рождения: {data['driver_birth_date']}, ошибка: {str(e)}")
                    # Устанавливаем текущую дату
                    driver_data["birth_date"] = datetime.now().date()
                    print(f"⚠️ Использована текущая дата вместо даты рождения: {driver_data['birth_date']}")
        else:
            # Если дата рождения не указана, устанавливаем текущую дату
            from datetime import datetime
            driver_data["birth_date"] = datetime.now().date()
            print(f"⚠️ Дата рождения не указана, использована текущая дата: {driver_data['birth_date']}")
        
        # Устанавливаем дату выдачи ВУ, если она указана
        if data.get('driver_license_issue_date'):
            try:
                from datetime import datetime
                license_issue_date = datetime.strptime(data['driver_license_issue_date'], "%d.%m.%Y").date()
                driver_data["driver_license_issue_date"] = license_issue_date
                print(f"Установлена дата выдачи ВУ: {license_issue_date}")
            except ValueError:
                try:
                    # Пробуем альтернативный формат
                    license_issue_date = datetime.strptime(data['driver_license_issue_date'], "%Y-%m-%d").date()
                    driver_data["driver_license_issue_date"] = license_issue_date
                    print(f"Установлена дата выдачи ВУ (альт. формат): {license_issue_date}")
                except ValueError:
                    print(f"Не удалось преобразовать дату выдачи ВУ: {data['driver_license_issue_date']}")
                    # Сохраняем строковое значение
                    driver_data["driver_license_issue_date"] = data['driver_license_issue_date']
        
        print(f"Подготовлены данные водителя: {driver_data}")
        
        # Если водитель уже существует, обновляем его данные
        if existing_driver:
            print(f"Обновляем существующего водителя с ID: {existing_driver.id}")
            driver = crud.update_driver(db, existing_driver.id, driver_data)
        else:
            # Иначе создаем нового водителя
            print(f"Создаем нового водителя с данными: {driver_data}")
            try:
                driver = crud.create_driver(db, schemas.DriverCreate(**driver_data))
                print(f"✅ Водитель успешно создан с ID: {driver.id}")
                print(f"✅ Параметры созданного водителя: ID={driver.id}, Name={driver.full_name}, Phone={driver.phone}, Status={driver.status}")
                
                # Проверка ID водителя
                if not driver.id:
                    print("❌ КРИТИЧЕСКАЯ ОШИБКА: ID водителя не получен!")
                    return {"status": "error", "message": "Ошибка при создании водителя: не получен ID"}
            except Exception as e:
                print(f"❌ ОШИБКА при создании водителя: {str(e)}")
                import traceback
                print(traceback.format_exc())
                return {"status": "error", "message": f"Ошибка при создании водителя: {str(e)}"}
        
        # Связываем пользователя с водителем
        try:
            user.driver_id = driver.id
            db.commit()
            print(f"✅ Пользователь связан с водителем: user_id={user.id}, driver_id={driver.id}")
        except Exception as e:
            print(f"❌ ОШИБКА при связывании пользователя с водителем: {str(e)}")
            db.rollback()
            import traceback
            print(traceback.format_exc())
            return {"status": "error", "message": f"Ошибка при связывании пользователя с водителем: {str(e)}"}
        
        # Получаем данные об автомобиле из JSON
        car_data = {
            "driver_id": driver.id,
            "brand": data.get('driver_car_brand', ''),
            "model": data.get('driver_car_model', ''),
            "year": int(data.get('driver_car_year', 2020)) if data.get('driver_car_year', '').isdigit() else 2020,
            "color": data.get('driver_car_color', ''),
            "transmission": data.get('driver_car_transmission', ''),
            "license_plate": data.get('driver_car_number', ''),
            "vin": data.get('driver_car_vin', ''),
            "sts": data.get('driver_car_sts', ''),
            "tariff": data.get('driver_car_category', 'comfort'),
            "service_type": "Такси",
            "has_booster": data.get('driver_car_boosters', '0') != '0',
            "has_child_seat": data.get('driver_car_child_seats', '0') != '0'
        }
        
        print(f"Подготовлены данные автомобиля: {car_data}")
        
        # Создаем автомобиль
        existing_car = db.query(models.Car).filter(models.Car.driver_id == driver.id).first()
        
        if existing_car:
            print(f"Обновляем существующий автомобиль: {existing_car.id}")
            car = crud.update_car(db, existing_car.id, car_data)
        else:
            print(f"Создаем новый автомобиль для водителя: {driver.id}")
            try:
                car = crud.create_car(db, schemas.CarCreate(**car_data), driver_id=driver.id)
                print(f"✅ Автомобиль успешно создан с ID: {car.id}")
                print(f"✅ Параметры созданного автомобиля: ID={car.id}, Brand={car.brand}, Model={car.model}, Year={car.year}")
            except Exception as e:
                print(f"❌ ОШИБКА при создании автомобиля: {str(e)}")
                import traceback
                print(traceback.format_exc())
        
        # Проверка, что водитель создан и связан с пользователем
        try:
            user_after = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
            if user_after and user_after.driver_id:
                print(f"✅ Пользователь {user_after.id} связан с водителем {user_after.driver_id}")
                
                # Дополнительная проверка
                driver_after = db.query(models.Driver).filter(models.Driver.id == user_after.driver_id).first()
                if driver_after:
                    print(f"✅ Водитель {driver_after.id} существует и имеет имя {driver_after.full_name}")
                else:
                    print(f"⚠️ Водитель с ID {user_after.driver_id} не найден в базе данных!")
            else:
                print(f"⚠️ Пользователь {user_id} НЕ связан с водителем!")
        except Exception as e:
            print(f"❌ ОШИБКА при проверке: {str(e)}")
        
        return {"status": "success", "driver_id": driver.id}
        
    except Exception as e:
        db.rollback()
        import traceback
        trace = traceback.format_exc()
        print(f"Ошибка при регистрации водителя: {str(e)}\n{trace}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e), "trace": trace}
        )

@app.post("/api/driver/find-by-phone")
async def find_driver_by_phone(request: Request, db: Session = Depends(get_db)):
    """API для поиска водителя по номеру телефона"""
    try:
        # Получаем данные из запроса
        data = await request.json()
        phone = data.get('phone')
        
        if not phone:
            return JSONResponse(content={"status": "error", "message": "Не указан номер телефона"}, status_code=400)
        
        # Ищем водителя по номеру телефона
        driver = crud.get_driver_by_phone(db, phone)
        
        if driver:
            # Если нашли водителя, возвращаем его ID
            print(f"Найден водитель по телефону {phone}, ID: {driver.id}")
            return {"status": "success", "driver_id": driver.id}
        
        # Если водитель не найден, ищем пользователя по телефону
        user = crud.get_driver_user_by_phone(db, phone)
        
        if user and user.driver_id:
            # Если у пользователя есть связанный водитель, возвращаем его ID
            print(f"Найден пользователь по телефону {phone}, driver_id: {user.driver_id}")
            return {"status": "success", "driver_id": user.driver_id}
        
        # Если никого не нашли, возвращаем ошибку
        print(f"Водитель не найден по телефону {phone}")
        return {"status": "error", "message": "Водитель не найден"}
    except Exception as e:
        print(f"Ошибка при поиске водителя по телефону: {str(e)}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/driver/{driver_id}/profile")
async def get_driver_profile(driver_id: str, db: Session = Depends(get_db)):
    """
    Получение данных профиля водителя для отображения в профиле
    """
    try:
        print(f"Запрос профиля для водителя с ID: {driver_id}")
        
        # Получаем данные водителя из БД
        driver = crud.get_driver(db, driver_id)
        if not driver:
            return JSONResponse(
                status_code=404,
                content={"message": "Водитель не найден"}
            )
        
        # Получаем данные об автомобиле
        car = driver.car if hasattr(driver, 'car') and driver.car else None
        car_data = None
        
        if car:
            car_data = {
                "brand": car.brand,
                "model": car.model,
                "number": car.number,
                "sts": car.sts if hasattr(car, 'sts') else None
            }
        
        # Получаем данные о парке такси
        park_name = "ООО Тумар Такси"  # Пример, в реальности должно быть из БД
        
        # Вычисляем рейтинг и активность (в реальности из БД)
        # Пример: рейтинг от 0 до 5000, активность - число выполненных заказов
        rating = "5,000"
        activity = 39
        
        # Если есть реальные данные о рейтинге и активности в БД, используем их
        if hasattr(driver, 'rating') and driver.rating is not None:
            rating = str(driver.rating)
        
        if hasattr(driver, 'activity') and driver.activity is not None:
            activity = driver.activity
        
        # Формируем ответ
        return {
            "id": driver.id,
            "full_name": driver.full_name,
            "phone": driver.phone,
            "car": car_data,
            "park": park_name,
            "rating": rating,
            "activity": activity
        }
    except Exception as e:
        print(f"Ошибка при получении профиля водителя: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Ошибка сервера: {str(e)}"}
        )

@app.get("/api/driver/{driver_id}/stats")
async def get_driver_stats(driver_id: str, date: str = None, db: Session = Depends(get_db)):
    """
    Получение статистики водителя за определенную дату
    """
    try:
        print(f"Запрос статистики для водителя с ID: {driver_id}, дата: {date}")
        
        # Получаем данные водителя из БД
        driver = crud.get_driver(db, driver_id)
        if not driver:
            return JSONResponse(
                status_code=404,
                content={"message": "Водитель не найден"}
            )
        
        # Если дата не указана, используем текущую
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # Парсим дату
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"message": "Неверный формат даты. Используйте YYYY-MM-DD"}
            )
        
        # Получаем начало и конец дня для запроса
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        
        # В реальности здесь должен быть запрос к БД для получения заказов водителя за указанную дату
        # Пример: orders = crud.get_driver_orders(db, driver_id, day_start, day_end)
        
        # Для демонстрации создаем фиктивные данные
        # В реальном приложении эти данные должны быть получены из БД
        
        # Проверяем, является ли выбранная дата сегодняшним днем
        is_today = target_date.date() == datetime.now().date()
        
        # Создаем тестовые данные в зависимости от даты
        if is_today:
            # Для текущего дня показываем нулевой баланс
            orders_count = 0
            balance = 0.0
            cash = 0
            card = 0
            service = 0
            service_percent = 0
        else:
            # Для прошлых дней генерируем случайные данные на основе дня месяца
            day_of_month = target_date.day
            orders_count = day_of_month % 10  # От 0 до 9 заказов
            balance = day_of_month * 100.0  # Баланс пропорционален дню месяца
            cash = int(balance * 0.7)  # 70% наличными
            card = int(balance * 0.3)  # 30% по карте
            service = int(balance * 0.15)  # 15% сервисный сбор
            service_percent = 15
        
        # Формируем ответ
        return {
            "date": date,
            "orders_count": orders_count,
            "balance": balance,
            "cash": cash,
            "card": card,
            "service": service,
            "service_percent": service_percent
        }
    except Exception as e:
        print(f"Ошибка при получении статистики водителя: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"message": f"Ошибка сервера: {str(e)}"}
        )

@app.get("/api/driver/{driver_id}/balance")
async def get_driver_balance(driver_id: str, db: Session = Depends(get_db)):
    """API для получения баланса водителя по ID"""
    try:
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return {"success": False, "detail": "Водитель не найден"}
            
        return {
            "success": True,
            "balance": driver.balance,
            "driver_id": driver.id,
            "full_name": driver.full_name
        }
    except Exception as e:
        return {"success": False, "detail": str(e)}

# Прямой вход по номеру телефона (для тестирования)
@app.get("/driver/direct-login/{phone}", response_class=HTMLResponse)
async def driver_direct_login(
    request: Request,
    phone: str,
    db: Session = Depends(get_db),
    response: Response = None
):
    """Прямой вход в систему по номеру телефона без проверки кода"""
    # Форматируем номер телефона - удаляем все кроме цифр
    phone_digits = ''.join(filter(str.isdigit, phone))
    
    # Добавляем "+" в начале, если его нет
    if not phone.startswith('+'):
        phone = '+' + phone
    
    print(f"Прямой вход для номера телефона: {phone}, digits: {phone_digits}")
    
    # Ищем пользователя
    user = crud.get_driver_user_by_phone(db, phone_digits)
    
    # Если пользователя нет, создаем его
    if not user:
        print(f"Пользователь с телефоном {phone_digits} не найден. Создаем нового.")
        user = crud.create_driver_user(db, schemas.DriverUserCreate(phone=phone_digits))
        print(f"Создан новый пользователь с id={user.id}")
    else:
        print(f"Найден существующий пользователь с id={user.id}, driver_id={user.driver_id}")
    
    # Проверяем наличие водителя, связанного с пользователем
    driver_id = user.driver_id
    has_driver = driver_id is not None
    
    print(f"Связанный водитель: driver_id={driver_id}, has_driver={has_driver}")
    
    # Если driver_id не найден, ищем водителя по номеру телефона
    if not has_driver:
        print(f"Поиск водителя по номеру телефона: {phone}")
        # Попробуем разные форматы телефона
        phone_formats = [
            phone_digits,                          # Без +
            '+' + phone_digits,                    # С +
            '996' + phone_digits[3:] if phone_digits.startswith('996') else phone_digits,  # Без 996 в начале
            phone.replace('-', ''),                # Без дефисов
            phone.replace(' ', '')                 # Без пробелов
        ]
        
        for phone_format in phone_formats:
            print(f"Проверка формата телефона: {phone_format}")
            driver = db.query(models.Driver).filter(models.Driver.phone == phone_format).first()
            if driver:
                # Связываем пользователя с водителем
                print(f"Найден водитель по телефону {phone_format}: id={driver.id}, name={driver.full_name}")
                user.driver_id = driver.id
                db.commit()
                
                driver_id = driver.id
                has_driver = True
                print(f"Связали пользователя id={user.id} с водителем id={driver.id}")
                break
        
        if not has_driver:
            print(f"Водитель с телефоном {phone} и похожими форматами не найден")
    else:
        print(f"Проверка существующего водителя с id={driver_id}")
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if driver:
            print(f"Найден связанный водитель: id={driver.id}, name={driver.full_name}")
        else:
            print(f"Ошибка: связанный водитель с id={driver_id} не найден в базе данных")
    
    # Создаем JWT токен
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"user_id": user.id, "phone": phone_digits},
        expires_delta=access_token_expires
    )
    
    print(f"Создан токен для пользователя id={user.id}, has_driver={has_driver}, driver_id={driver_id}")
    
    # Создаем редирект
    redirect_url = "/driver/profile" if has_driver else "/driver/survey/1"
    response = RedirectResponse(url=redirect_url, status_code=303)
    
    # Устанавливаем куки с JWT токеном
    response.set_cookie(
        key="token",
        value=access_token,
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="strict"
    )
    
    print(f"Установлен токен в куки, перенаправление на {redirect_url}")
    return response

# Эндпоинт для синхронизации водителей из административной панели
@app.get("/api/sync-drivers", response_model=dict)
async def sync_drivers(db: Session = Depends(get_db)):
    """
    Синхронизирует данные водителей из таблицы drivers в таблицу driver_users.
    Создает пользователей для водителей, которые есть в таблице drivers, но нет в driver_users.
    """
    try:
        # Получаем всех водителей из таблицы drivers
        drivers = db.query(models.Driver).all()
        print(f"Найдено {len(drivers)} водителей для синхронизации")
        
        # Счетчики для статистики
        created_count = 0
        linked_count = 0
        already_linked_count = 0
        
        # Обрабатываем каждого водителя
        for driver in drivers:
            # Пропускаем водителей без телефона
            if not driver.phone:
                print(f"Водитель id={driver.id}, {driver.full_name} не имеет телефона, пропускаем")
                continue
                
            print(f"Обработка водителя: id={driver.id}, name={driver.full_name}, phone={driver.phone}")
            
            # Нормализуем формат телефона для поиска
            phone_digits = ''.join(filter(str.isdigit, driver.phone))
                
            # Ищем пользователя с таким номером телефона
            user = db.query(models.DriverUser).filter(models.DriverUser.phone == phone_digits).first()
            
            if user:
                print(f"Найден пользователь id={user.id}, phone={user.phone}")
                
                # Проверяем, связан ли пользователь с этим водителем
                if user.driver_id == driver.id:
                    print(f"Пользователь уже связан с этим водителем")
                    already_linked_count += 1
                elif user.driver_id is None:
                    # Связываем пользователя с водителем
                    user.driver_id = driver.id
                    print(f"Связали пользователя id={user.id} с водителем id={driver.id}")
                    linked_count += 1
                else:
                    print(f"Пользователь связан с другим водителем id={user.driver_id}, пропускаем")
            else:
                # Создаем нового пользователя
                new_user = models.DriverUser(
                    phone=phone_digits,
                    first_name=driver.full_name.split()[0] if ' ' in driver.full_name else driver.full_name,
                    last_name=' '.join(driver.full_name.split()[1:]) if ' ' in driver.full_name else "",
                    is_verified=True,
                    driver_id=driver.id
                )
                db.add(new_user)
                print(f"Создан новый пользователь для водителя id={driver.id}")
                created_count += 1
        
        # Сохраняем изменения в БД
        db.commit()
        
        return {
            "success": True,
            "total_drivers": len(drivers),
            "created_users": created_count,
            "linked_users": linked_count,
            "already_linked": already_linked_count
        }
    except Exception as e:
        db.rollback()
        print(f"Ошибка при синхронизации: {str(e)}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/test-db-connection", response_model=dict)
async def test_db_connection(db: Session = Depends(get_db)):
    """
    Тестирование соединения с базой данных и проверка доступа к таблицам
    """
    try:
        result = {
            "status": "success",
            "message": "Проверка соединения с базой данных и таблицами",
            "tables": {}
        }
        
        # Проверка доступа к таблице drivers
        try:
            drivers_count = db.query(func.count(models.Driver.id)).scalar()
            sample_drivers = db.query(models.Driver).limit(5).all()
            
            result["tables"]["drivers"] = {
                "count": drivers_count,
                "sample_data": [
                    {
                        "id": driver.id,
                        "full_name": driver.full_name,
                        "phone": driver.phone,
                        "status": driver.status
                    } for driver in sample_drivers
                ]
            }
        except Exception as e:
            result["tables"]["drivers"] = {
                "error": str(e)
            }
            
        # Проверка доступа к таблице DriverUsers
        try:
            users_count = db.query(func.count(models.DriverUser.id)).scalar()
            sample_users = db.query(models.DriverUser).limit(5).all()
            
            result["tables"]["driver_users"] = {
                "count": users_count,
                "sample_data": [
                    {
                        "id": user.id,
                        "phone": user.phone,
                        "first_name": user.first_name,
                        "driver_id": user.driver_id
                    } for user in sample_users
                ]
            }
        except Exception as e:
            result["tables"]["driver_users"] = {
                "error": str(e)
            }
            
        # Проверка связей между таблицами
        try:
            linked_users = db.query(models.DriverUser).filter(models.DriverUser.driver_id != None).limit(5).all()
            
            result["user_driver_links"] = [
                {
                    "user_id": user.id,
                    "user_phone": user.phone,
                    "driver_id": user.driver_id
                } for user in linked_users
            ]
        except Exception as e:
            result["user_driver_links"] = {
                "error": str(e)
            }
        
        return result
    
    except Exception as e:
        return {
            "status": "error",
            "message": "Ошибка при проверке соединения с базой данных",
            "error": str(e)
        }

@app.get("/api/sync-driver-users", response_model=dict)
async def sync_driver_users(db: Session = Depends(get_db)):
    """
    Синхронизирует данные между таблицами drivers и DriverUsers.
    Для каждого водителя с телефоном ищет или создает запись в DriverUsers
    и связывает их.
    """
    try:
        # Статистика синхронизации
        stats = {
            "total_drivers": 0,
            "drivers_with_phone": 0,
            "users_created": 0,
            "users_linked": 0,
            "already_linked": 0,
            "details": []
        }
        
        # Получаем всех водителей
        drivers = db.query(models.Driver).all()
        stats["total_drivers"] = len(drivers)
        
        for driver in drivers:
            driver_info = {
                "driver_id": driver.id,
                "full_name": driver.full_name,
                "phone": driver.phone,
                "action": "skipped"
            }
            
            # Пропускаем водителей без телефона
            if not driver.phone:
                driver_info["reason"] = "no_phone"
                stats["details"].append(driver_info)
                continue
                
            stats["drivers_with_phone"] += 1
            
            # Очищаем номер телефона от всего кроме цифр
            cleaned_phone = ''.join(filter(str.isdigit, driver.phone))
            
            # Проверяем, существует ли уже пользователь с таким телефоном
            existing_user = crud.get_driver_user_by_phone(db, cleaned_phone)
            
            if existing_user:
                if existing_user.driver_id:
                    # Пользователь уже связан с водителем
                    if existing_user.driver_id == driver.id:
                        driver_info["action"] = "already_linked"
                        driver_info["user_id"] = existing_user.id
                        stats["already_linked"] += 1
                    else:
                        # Пользователь связан с другим водителем
                        driver_info["action"] = "already_linked_to_other"
                        driver_info["user_id"] = existing_user.id
                        driver_info["linked_driver_id"] = existing_user.driver_id
                else:
                    # Обновляем пользователя, связывая его с водителем
                    existing_user.driver_id = driver.id
                    db.commit()
                    
                    driver_info["action"] = "linked"
                    driver_info["user_id"] = existing_user.id
                    stats["users_linked"] += 1
            else:
                # Создаем нового пользователя и связываем с водителем
                user_data = {
                    "phone": cleaned_phone,
                    "first_name": driver.full_name.split()[0] if driver.full_name else "",
                    "last_name": " ".join(driver.full_name.split()[1:]) if driver.full_name and len(driver.full_name.split()) > 1 else "",
                    "is_verified": True,
                    "date_registered": datetime.now(),
                    "last_login": datetime.now(),
                    "driver_id": driver.id
                }
                
                new_user = crud.create_driver_user(db, user_data)
                
                driver_info["action"] = "created"
                driver_info["user_id"] = new_user.id
                stats["users_created"] += 1
                
            stats["details"].append(driver_info)
        
        return {
            "status": "success",
            "message": "Синхронизация выполнена успешно",
            "stats": stats
        }
    
    except Exception as e:
        return {
            "status": "error",
            "message": "Ошибка при синхронизации",
            "error": str(e)
        }

@app.get("/api/driver/{driver_id}/sync-balance", response_model=dict)
async def sync_driver_balance(driver_id: int, db: Session = Depends(get_db)):
    """
    Проверяет и синхронизирует баланс водителя между таблицами
    """
    try:
        # Получаем водителя по ID
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return {
                "status": "error",
                "message": "Водитель не найден",
                "driver_id": driver_id
            }
            
        # Получаем информацию о связанном аккаунте пользователя
        user = db.query(models.DriverUser).filter(models.DriverUser.driver_id == driver_id).first()
        
        # Получаем последние транзакции
        transactions = db.query(models.BalanceTransaction).filter(
            models.BalanceTransaction.driver_id == driver_id
        ).order_by(models.BalanceTransaction.created_at.desc()).limit(10).all()
        
        # Общая сумма транзакций (для проверки)
        total_transactions = db.query(func.sum(models.BalanceTransaction.amount)).filter(
            models.BalanceTransaction.driver_id == driver_id
        ).scalar() or 0
        
        # Проверяем расхождение между балансом и суммой транзакций
        balance_discrepancy = driver.balance - total_transactions
        
        # Результат проверки
        result = {
            "status": "success",
            "driver_id": driver_id,
            "full_name": driver.full_name,
            "phone": driver.phone,
            "current_balance": driver.balance,
            "transactions_sum": total_transactions,
            "balance_discrepancy": balance_discrepancy,
            "has_user_account": user is not None,
            "recent_transactions": [
                {
                    "id": tx.id,
                    "amount": tx.amount,
                    "type": tx.type,
                    "created_at": tx.created_at.isoformat() if tx.created_at else None,
                    "description": tx.description
                } for tx in transactions
            ]
        }
        
        # Если есть расхождение в балансе, исправляем
        if abs(balance_discrepancy) > 0.01:  # Учитываем возможную погрешность из-за округления
            # Создаем корректирующую транзакцию
            correction_tx = models.BalanceTransaction(
                driver_id=driver_id,
                amount=balance_discrepancy,
                type="correction",
                description=f"Автоматическая корректировка баланса ({balance_discrepancy:.2f})"
            )
            db.add(correction_tx)
            
            # Обновляем баланс, если есть аккаунт пользователя
            if user and user.driver_id:
                # TODO: Если есть отдельная таблица для баланса пользователя,
                # обновить и ее здесь
                pass
                
            result["correction_applied"] = True
            result["correction_amount"] = balance_discrepancy
            
            # Фиксируем изменения в БД
            db.commit()
        else:
            result["correction_applied"] = False
            
        return result
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Ошибка при синхронизации баланса: {str(e)}",
            "driver_id": driver_id
        }

@app.get("/driver/balance", response_class=HTMLResponse)
async def driver_balance_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница баланса и истории транзакций водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        print(f"Декодирование токена: {token[:20]}...")
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        print(f"Токен декодирован, user_id={user_id}")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            print(f"Пользователь с id={user_id} не найден, перенаправление на страницу авторизации")
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            print(f"Пользователь id={user.id} не связан с водителем, перенаправление на анкету")
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            print(f"Водитель с id={user.driver_id} не найден, перенаправление на анкету")
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем историю транзакций
        transactions = db.query(models.BalanceTransaction).filter(
            models.BalanceTransaction.driver_id == driver.id
        ).order_by(models.BalanceTransaction.created_at.desc()).all()
        
        # Преобразуем транзакции для отображения
        transaction_list = []
        for tx in transactions:
            # Определяем тип операции для отображения
            operation_type = "Пополнение"
            if tx.type == "withdrawal":
                operation_type = "Вывод средств"
            elif tx.type == "commission":
                operation_type = "Комиссия"
            elif tx.type == "correction":
                operation_type = "Корректировка"
                
            # Определяем класс для стилизации (положительные/отрицательные суммы)
            amount_class = "positive" if tx.amount >= 0 else "negative"
            
            # Форматируем дату
            tx_date = tx.created_at.strftime("%d.%m.%Y %H:%M") if tx.created_at else "Нет даты"
            
            transaction_list.append({
                "id": tx.id,
                "date": tx_date,
                "type": operation_type,
                "amount": tx.amount,
                "amount_formatted": f"{'+' if tx.amount >= 0 else ''}{tx.amount:.2f}",
                "description": tx.description or "",
                "amount_class": amount_class
            })
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver,
            "balance": driver.balance,
            "balance_formatted": f"{driver.balance:.2f}",
            "transactions": transaction_list,
            "driver_name": f"{user.first_name} {user.last_name}",
            "driver_id": driver.id
        }
        
        return templates.TemplateResponse("driver/profile/balance.html", template_data)
        
    except jose.jwt.JWTError as e:
        print(f"Ошибка проверки JWT: {str(e)}")
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы баланса: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/balance/top-up", response_class=HTMLResponse)
async def driver_balance_top_up(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница пополнения баланса водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Форматируем баланс
        balance_formatted = f"{driver.balance:.2f}"
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver,
            "balance": driver.balance,
            "balance_formatted": balance_formatted
        }
        
        return templates.TemplateResponse("driver/profile/top-up.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы пополнения баланса: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.post("/api/driver/balance/top-up", response_model=dict)
async def api_driver_balance_top_up(request: Request, db: Session = Depends(get_db)):
    """API для пополнения баланса водителя"""
    try:
        # Получаем данные из запроса
        data = await request.json()
        driver_id = data.get("driver_id")
        amount = data.get("amount")
        
        if not driver_id or not amount:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Не указан ID водителя или сумма пополнения"}
            )
        
        # Преобразуем сумму в число
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Некорректная сумма пополнения"}
            )
        
        # Проверяем минимальную сумму
        if amount < 10:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Минимальная сумма пополнения - 10 сом"}
            )
        
        # Получаем водителя по ID
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Водитель не найден"}
            )
        
        # Пополняем баланс
        driver.balance += amount
        
        # Создаем запись о транзакции
        transaction = models.BalanceTransaction(
            driver_id=driver.id,
            amount=amount,
            type="deposit",
            status="completed",
            description=f"Пополнение баланса через мобильное приложение"
        )
        
        db.add(transaction)
        db.commit()
        
        return {
            "success": True, 
            "message": "Баланс успешно пополнен", 
            "new_balance": driver.balance,
            "transaction_id": transaction.id
        }
    
    except Exception as e:
        db.rollback()
        print(f"Ошибка при пополнении баланса: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Ошибка сервера: {str(e)}"}
        )

# Обновляем функцию для получения баланса
@app.get("/api/driver/{driver_id}/balance")
async def get_driver_balance(driver_id: str, db: Session = Depends(get_db)):
    """API для получения баланса водителя по ID"""
    try:
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return {"success": False, "detail": "Водитель не найден"}
            
        # Получаем последние транзакции
        transactions = db.query(models.BalanceTransaction).filter(
            models.BalanceTransaction.driver_id == driver.id
        ).order_by(models.BalanceTransaction.created_at.desc()).limit(5).all()
        
        # Форматируем транзакции
        transaction_list = []
        for tx in transactions:
            operation_type = "Пополнение"
            if tx.type == "withdrawal":
                operation_type = "Вывод средств"
            elif tx.type == "commission":
                operation_type = "Комиссия"
            elif tx.type == "correction":
                operation_type = "Корректировка"
                
            tx_date = tx.created_at.strftime("%d.%m.%Y %H:%M") if tx.created_at else "Нет даты"
            
            transaction_list.append({
                "id": tx.id,
                "date": tx_date,
                "type": operation_type,
                "amount": tx.amount,
                "amount_formatted": f"{'+' if tx.amount >= 0 else ''}{tx.amount:.2f}"
            })
            
        return {
            "success": True,
            "balance": driver.balance,
            "balance_formatted": f"{driver.balance:.2f}",
            "driver_id": driver.id,
            "full_name": driver.full_name,
            "recent_transactions": transaction_list
        }
    except Exception as e:
        print(f"Ошибка при получении баланса: {str(e)}")
        return {"success": False, "detail": str(e)}

@app.get("/driver/data", response_class=HTMLResponse)
async def driver_data_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница личных данных водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Отладочный вывод состояния даты рождения и даты выдачи прав
        print(f"Исходная дата рождения: {driver.birth_date}, тип: {type(driver.birth_date)}")
        print(f"Исходная дата выдачи ВУ: {driver.driver_license_issue_date}, тип: {type(driver.driver_license_issue_date)}")
        
        # Проверяем и конвертируем birth_date, если это строка
        if driver.birth_date and isinstance(driver.birth_date, str):
            try:
                # Пробуем формат "DD.MM.YYYY"
                driver.birth_date = datetime.strptime(driver.birth_date, "%d.%m.%Y").date()
                print(f"Успешно преобразована дата рождения: {driver.birth_date}")
            except ValueError:
                try:
                    # Пробуем альтернативный формат "YYYY-MM-DD"
                    driver.birth_date = datetime.strptime(driver.birth_date, "%Y-%m-%d").date()
                    print(f"Успешно преобразована дата рождения (альт. формат): {driver.birth_date}")
                except ValueError:
                    # Если не удалось преобразовать, оставляем как есть (строку)
                    print(f"Не удалось преобразовать дату рождения: {driver.birth_date}")
        
        # Проверяем и конвертируем driver_license_issue_date, если это строка
        if driver.driver_license_issue_date and isinstance(driver.driver_license_issue_date, str):
            try:
                # Пробуем формат "DD.MM.YYYY"
                driver.driver_license_issue_date = datetime.strptime(driver.driver_license_issue_date, "%d.%m.%Y").date()
                print(f"Успешно преобразована дата выдачи ВУ: {driver.driver_license_issue_date}")
            except ValueError:
                try:
                    # Пробуем альтернативный формат "YYYY-MM-DD"
                    driver.driver_license_issue_date = datetime.strptime(driver.driver_license_issue_date, "%Y-%m-%d").date()
                    print(f"Успешно преобразована дата выдачи ВУ (альт. формат): {driver.driver_license_issue_date}")
                except ValueError:
                    # Если не удалось преобразовать, оставляем как есть (строку)
                    print(f"Не удалось преобразовать дату выдачи ВУ: {driver.driver_license_issue_date}")
        
        # Устанавливаем временное значение для даты выдачи ВУ, если она отсутствует
        if not driver.driver_license_issue_date:
            # Если license_issue_date существует, используем его
            if hasattr(driver, 'license_issue_date') and driver.license_issue_date:
                print(f"Используем license_issue_date: {driver.license_issue_date}")
                driver.driver_license_issue_date = driver.license_issue_date
            else:
                # Устанавливаем фиксированную дату для отладки
                print("Устанавливаем временную дату выдачи ВУ для отладки")
                driver.driver_license_issue_date = "01.01.2020"
        
        # Получаем данные автомобиля
        car = db.query(models.Car).filter(models.Car.driver_id == driver.id).first()
        
        if car and not car.tariff and driver.tariff:
            # Если у машины не указан тариф, но у водителя он есть, обновляем его
            car.tariff = driver.tariff
            db.commit()
            print(f"Обновлен тариф автомобиля: {car.tariff}")
        
        # Получаем пути к фотографиям документов
        driver_id_str = str(driver.id)
        base_uploads_path = "/uploads/drivers"
        docs_photos = {
            "passport_front": f"{base_uploads_path}/{driver_id_str}/passport_front.jpg" if hasattr(driver, "passport_front_path") and driver.passport_front_path else None,
            "passport_back": f"{base_uploads_path}/{driver_id_str}/passport_back.jpg" if hasattr(driver, "passport_back_path") and driver.passport_back_path else None,
            "license_front": f"{base_uploads_path}/{driver_id_str}/license_front.jpg" if hasattr(driver, "license_front_path") and driver.license_front_path else None,
            "license_back": f"{base_uploads_path}/{driver_id_str}/license_back.jpg" if hasattr(driver, "license_back_path") and driver.license_back_path else None
        }
        
        # Получаем пути к фотографиям автомобиля
        car_photos = {}
        if car:
            car_photos = {
                "front": car.photo_front,
                "rear": car.photo_rear,
                "right": car.photo_right,
                "left": car.photo_left,
                "interior_front": car.photo_interior_front,
                "interior_rear": car.photo_interior_rear
            }
        
        # Подготовка даты для шаблона
        license_issue_date = None
        
        if driver.driver_license_issue_date:
            if hasattr(driver.driver_license_issue_date, 'strftime'):
                license_issue_date = driver.driver_license_issue_date.strftime('%d.%m.%Y')
            else:
                license_issue_date = str(driver.driver_license_issue_date)
            
            print(f"Дата выдачи ВУ для шаблона: {license_issue_date}")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver,
            "car": car,
            "docs_photos": docs_photos,
            "car_photos": car_photos,
            "license_issue_date": license_issue_date  # Добавляем отдельную переменную для даты
        }
        
        return templates.TemplateResponse("driver/profile/driver-data.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы личных данных: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/activity", response_class=HTMLResponse, name="driver_activity_page")
async def driver_activity_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница истории активности водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем заказы водителя за последнюю неделю
        week_ago = datetime.now() - timedelta(days=7)
        orders = db.query(models.Order).filter(
            models.Order.driver_id == driver.id,
            models.Order.created_at >= week_ago
        ).order_by(models.Order.created_at.desc()).all()
        
        # Форматируем заказы для отображения
        formatted_orders = []
        for order in orders:
            # Дата для группировки
            order_date = order.created_at.date()
            date_str = order_date.strftime("%d.%m.%Y")
            
            # Время заказа
            time_str = order.created_at.strftime("%H:%M")
            
            # Форматируем цену
            price_formatted = f"{order.price:.0f}" if hasattr(order, 'price') and order.price else "0"
            
            # Добавляем заказ в список
            formatted_orders.append({
                'id': order.id,
                'date_str': date_str,
                'time_str': time_str,
                'origin': order.origin,
                'destination': order.destination,
                'price': order.price,
                'price_formatted': price_formatted,
                'status': order.status,
                'payment_type': getattr(order, 'payment_type', 'cash'),
                'distance': getattr(order, 'distance', '0'),
                'duration': getattr(order, 'duration', '0 мин'),
                'tariff': getattr(order, 'tariff', 'Стандарт')
            })
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver,
            "orders": formatted_orders
        }
        
        return templates.TemplateResponse("driver/profile/activity.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке истории активности: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/api/driver/{driver_id}/activity", response_model=dict)
async def get_driver_activity(
    driver_id: str, 
    period: str = Query("week", regex="^(week|month|all)$"),
    db: Session = Depends(get_db)
):
    """API для получения истории заказов водителя"""
    try:
        # Проверяем, существует ли водитель
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return {"success": False, "message": "Водитель не найден"}
        
        # Определяем начальную дату для фильтрации
        start_date = None
        if period == "week":
            start_date = datetime.now() - timedelta(days=7)
        elif period == "month":
            start_date = datetime.now() - timedelta(days=30)
        
        # Запрос заказов
        query = db.query(models.Order).filter(models.Order.driver_id == driver.id)
        
        # Применяем фильтр по дате, если указан период
        if start_date:
            query = query.filter(models.Order.created_at >= start_date)
        
        # Получаем отсортированные заказы
        orders = query.order_by(models.Order.created_at.desc()).all()
        
        # Форматируем заказы
        formatted_orders = []
        for order in orders:
            # Дата для группировки
            order_date = order.created_at.date()
            date_str = order_date.strftime("%d.%m.%Y")
            
            # Время заказа
            time_str = order.created_at.strftime("%H:%M")
            
            # Форматируем цену
            price_formatted = f"{order.price:.0f}" if hasattr(order, 'price') and order.price else "0"
            
            # Добавляем заказ в список
            formatted_orders.append({
                'id': order.id,
                'date_str': date_str,
                'time_str': time_str,
                'origin': order.origin,
                'destination': order.destination,
                'price': order.price,
                'price_formatted': price_formatted,
                'status': order.status,
                'payment_type': getattr(order, 'payment_type', 'cash'),
                'distance': getattr(order, 'distance', '0'),
                'duration': getattr(order, 'duration', '0 мин'),
                'tariff': getattr(order, 'tariff', 'Стандарт')
            })
        
        return {
            "success": True,
            "orders": formatted_orders,
            "total_count": len(formatted_orders),
            "period": period
        }
        
    except Exception as e:
        print(f"Ошибка при получении истории активности: {str(e)}")
        return {"success": False, "message": str(e)}

@app.get("/driver/tarifs/1", response_class=HTMLResponse, name="driver_tarifs")
async def driver_tarifs_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница выбора тарифов для водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем список доступных тарифов из JSON-файла
        import json
        try:
            with open("fast/static/assets/js/driver_data.json", "r", encoding="utf-8") as f:
                driver_data = json.load(f)
                available_tariffs = driver_data.get("tariffs", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Ошибка при чтении файла с тарифами: {str(e)}")
            available_tariffs = ["Эконом", "Комфорт", "Комфорт+", "Бизнес", "Премиум"]
        
        # Формируем список тарифов с описаниями
        tariffs = []
        for tariff_name in available_tariffs:
            tariff = {
                "name": tariff_name,
                "description": f"Тариф {tariff_name} для пассажирских перевозок.",
                "available": True
            }
            
            # Добавляем требования в зависимости от тарифа
            if tariff_name == "Комфорт":
                tariff["requirements"] = "Автомобиль не старше 7 лет, кондиционер, 4 двери."
            elif tariff_name == "Комфорт+":
                tariff["requirements"] = "Автомобиль не старше 5 лет, вместимость не менее 6 человек."
            elif tariff_name == "Бизнес":
                tariff["requirements"] = "Автомобиль премиум-класса не старше 3 лет, кожаный салон."
            elif tariff_name == "Премиум":
                tariff["requirements"] = "Премиальный автомобиль представительского класса."
            
            tariffs.append(tariff)
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver,
            "tariffs": tariffs
        }
        
        return templates.TemplateResponse("driver/tarifs/1.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы тарифов: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/tarifs/2", response_class=HTMLResponse, name="driver_tarif_options")
async def driver_tarif_options_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница опций для тарифов водителя"""
    if not token:
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные о машине водителя
        cars = db.query(models.Car).filter(models.Car.driver_id == driver.id).all()
        
        # Отладочный вывод для проверки данных из БД
        print(f"Найдено {len(cars)} автомобилей для водителя {driver.id}")
        for car in cars:
            print(f"Автомобиль {car.id}: has_sticker={car.has_sticker}, has_lightbox={car.has_lightbox}")
        
        # Определяем значения опций на основе данных из БД
        has_child_seat = False
        has_sticker = False
        has_lightbox = False
        
        for car in cars:
            if getattr(car, 'has_child_seat', False):
                has_child_seat = True
            if getattr(car, 'has_sticker', False):
                has_sticker = True
            if getattr(car, 'has_lightbox', False):
                has_lightbox = True
        
        # Получаем опции водителя из БД или создаем список опций по умолчанию
        options = [
            {
                "id": "pets",
                "name": "Перевозка домашних животных",
                "description": "Разрешить перевозку домашних животных в вашем автомобиле",
                "locked": True,
                "locked_message": "Выполните 10 заказов за неделю, чтобы разблокировать данную опцию",
                "enabled": False
            },
            {
                "id": "non_smoking",
                "name": "Некурящий салон",
                "description": "Запретить курение в салоне автомобиля",
                "locked": False,
                "enabled": True
            },
            {
                "id": "child_seat",
                "name": "Детское кресло",
                "description": "У вас есть детское кресло для перевозки детей",
                "locked": False,
                "enabled": has_child_seat
            },
            {
                "id": "booster",
                "name": "Бустер для детей",
                "description": "У вас есть бустер для перевозки детей",
                "locked": False,
                "enabled": driver.cars and any(car.has_booster for car in driver.cars) if hasattr(driver, 'cars') else False
            },
            {
                "id": "sticker",
                "name": "Наклейка",
                "description": "На автомобиле установлена наклейка сервиса",
                "locked": False,
                "enabled": has_sticker
            },
            {
                "id": "lightbox",
                "name": "Лайтбокс - Шашка",
                "description": "На автомобиле установлена шашка такси",
                "locked": False,
                "enabled": has_lightbox
            }
        ]
        
        # Отладочный вывод для проверки состояний опций перед отправкой в шаблон
        print("Значения опций перед отправкой в шаблон:")
        for option in options:
            print(f"  {option['id']}: {option['enabled']}")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver,
            "options": options,
            "has_sticker": has_sticker,    # Добавляем прямые значения для простоты в шаблоне
            "has_lightbox": has_lightbox,  # Добавляем прямые значения для простоты в шаблоне
            "has_child_seat": has_child_seat
        }
        
        return templates.TemplateResponse("driver/tarifs/2.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы опций тарифов: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.post("/api/driver/update-tariff", response_model=dict)
async def update_driver_tariff(request: Request, db: Session = Depends(get_db)):
    """API для обновления тарифа водителя"""
    try:
        # Получаем данные из запроса
        data = await request.json()
        driver_id = data.get("driver_id")
        tariff = data.get("tariff")
        
        if not driver_id or not tariff:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Не указан ID водителя или тариф"}
            )
        
        # Получаем водителя по ID
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Водитель не найден"}
            )
        
        # Обновляем тариф водителя
        old_tariff = driver.tariff
        driver.tariff = tariff
        
        print(f"Обновляем тариф водителя {driver_id} с {old_tariff} на {tariff}")
        
        # Также обновляем тариф для всех автомобилей водителя
        cars = db.query(models.Car).filter(models.Car.driver_id == driver_id).all()
        for car in cars:
            print(f"Обновляем тариф автомобиля {car.id} с {car.tariff} на {tariff}")
            car.tariff = tariff
        
        db.commit()
        
        return {
            "success": True, 
            "message": "Тариф успешно обновлен",
            "driver_id": driver.id,
            "tariff": tariff,
            "updated_cars": len(cars) if cars else 0
        }
    
    except Exception as e:
        db.rollback()
        print(f"Ошибка при обновлении тарифа: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Ошибка сервера: {str(e)}"}
        )

@app.post("/api/driver/update-option", response_model=dict)
async def update_driver_option(request: Request, db: Session = Depends(get_db)):
    """API для обновления опций водителя"""
    try:
        # Получаем данные из запроса
        data = await request.json()
        driver_id = data.get("driver_id")
        option_id = data.get("option_id")
        enabled = data.get("enabled")
        
        if not driver_id or not option_id or enabled is None:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "Не указаны обязательные параметры"}
            )
        
        # Получаем водителя по ID
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return JSONResponse(
                status_code=404,
                content={"success": False, "message": "Водитель не найден"}
            )
        
        # В зависимости от типа опции обновляем соответствующие поля
        # В реальном приложении здесь должно быть обновление соответствующей таблицы опций
        # Это упрощенный пример, который обновляет некоторые поля водителя
        
        if option_id == "child_seat" and driver.cars:
            for car in driver.cars:
                car.has_child_seat = enabled
                print(f"Обновлена опция has_child_seat={enabled} для автомобиля {car.id}")
        
        if option_id == "booster" and driver.cars:
            for car in driver.cars:
                car.has_booster = enabled
                print(f"Обновлена опция has_booster={enabled} для автомобиля {car.id}")
                
        if option_id == "sticker" and driver.cars:
            for car in driver.cars:
                car.has_sticker = enabled
                print(f"Обновлена опция has_sticker={enabled} для автомобиля {car.id}")
                
        if option_id == "lightbox" and driver.cars:
            for car in driver.cars:
                car.has_lightbox = enabled
                print(f"Обновлена опция has_lightbox={enabled} для автомобиля {car.id}")
        
        # Сохраняем изменения в БД
        db.commit()
        
        # Проверяем, что изменения сохранились
        updated_cars = []
        for car in driver.cars:
            db.refresh(car)
            car_info = {
                "id": car.id,
                "has_child_seat": car.has_child_seat,
                "has_booster": getattr(car, "has_booster", False),
                "has_sticker": car.has_sticker,
                "has_lightbox": car.has_lightbox
            }
            updated_cars.append(car_info)
            
        print(f"Проверка после сохранения: {updated_cars}")
        
        return {
            "success": True, 
            "message": "Опция успешно обновлена",
            "option_id": option_id,
            "enabled": enabled,
            "updated_cars": updated_cars
        }
    
    except Exception as e:
        db.rollback()
        print(f"Ошибка при обновлении опции: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Ошибка сервера: {str(e)}"}
        )

@app.get("/driver/support/1", response_class=HTMLResponse, name="driver_support")
async def driver_support_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница службы поддержки для водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/support/1.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы поддержки: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/support/2", response_class=HTMLResponse, name="driver_support_app_help")
async def driver_support_app_help_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница помощи с приложением"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/support/2.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы помощи с приложением: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/support/3", response_class=HTMLResponse)
async def driver_support_docs_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница информации о смене документов"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/support/3.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы смены документов: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/support/4", response_class=HTMLResponse)
async def driver_support_park_payment_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница 'Мне не платит парк-партнёр'"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/support/4.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы 'Мне не платит парк-партнёр': {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/support/5", response_class=HTMLResponse)
async def driver_support_lost_items_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница 'В машине остались вещи или посылка'"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/support/5.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы 'В машине остались вещи или посылка': {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/support/6", response_class=HTMLResponse)
async def driver_support_no_orders_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница 'Не получаю новые заказы'"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/support/6.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы 'Не получаю новые заказы': {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/support/7", response_class=HTMLResponse)
async def driver_support_access_closed_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница 'Почему закрыт доступ'"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/support/7.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы 'Почему закрыт доступ': {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/support/8", response_class=HTMLResponse)
async def driver_support_order_cost_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница 'У меня вопрос про расчет стоимости заказа'"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/support/8.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы 'У меня вопрос про расчет стоимости заказа': {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/diagnostics/1", response_class=HTMLResponse)
async def driver_diagnostics_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница диагностики для водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Проверка наличия тарифа
        has_tariff = driver.tariff is not None and driver.tariff.strip() != ""
        
        # Получаем фотографии документов
        photos = await get_driver_photos(driver.id, db)
        
        # Проверка фотоконтроля СТС через верификацию
        # Проверяем наличие верификации с типом photo_control и статусом accepted
        photo_verification = db.query(models.DriverVerification).filter(
            models.DriverVerification.driver_id == driver.id,
            models.DriverVerification.verification_type == "photo_control",
            models.DriverVerification.status == "accepted"
        ).first()
        
        car = driver.car
        # Если есть верификация со статусом accepted, значит фотоконтроль пройден
        sts_photo_passed = photo_verification is not None
        
        # Если нет верификации со статусом accepted, проверяем наличие СТС у автомобиля
        if not sts_photo_passed:
            sts_photo_passed = car is not None and hasattr(car, "sts") and car.sts is not None
        
        # Проверка фотоконтроля ВУ через ту же запись в DriverVerification
        # Используем ту же запись верификации, что и для СТС
        license_photo_passed = photo_verification is not None
        
        # Если нет верификации со статусом accepted, проверяем наличие фотографий водительского удостоверения
        if not license_photo_passed:
            license_photo_passed = photos.get("license_front") is not None and photos.get("license_back") is not None
        
        # Проверка баланса
        min_balance = 10
        balance = driver.balance or 0
        
        # Проверка наличия других ограничений (для примера)
        has_limitations = False  # Здесь должна быть логика проверки других ограничений
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver,
            "has_tariff": has_tariff,
            "sts_photo_passed": sts_photo_passed,
            "license_photo_passed": license_photo_passed,
            "balance": balance,
            "min_balance": min_balance,
            "has_limitations": has_limitations
        }
        
        return templates.TemplateResponse("driver/diagnostics/1.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы диагностики: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/diagnostics/2", response_class=HTMLResponse)
async def driver_low_balance_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница информации о низком балансе"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Определяем минимальный порог баланса
        min_balance = 10  # сом
        balance = driver.balance or 0
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver,
            "balance": balance,
            "min_balance": min_balance
        }
        
        return templates.TemplateResponse("driver/diagnostics/2.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы низкого баланса: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/diagnostics/3", response_class=HTMLResponse)
async def driver_limitations_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница с информацией о влиянии на заказы"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Пример возможных ограничений (в реальности должны загружаться из БД)
        limitations = [
            {
                "title": "Низкий рейтинг",
                "description": "Ваш рейтинг ниже среднего. Пассажиры чаще выбирают водителей с высоким рейтингом.",
                "action_url": "/driver/profile/rating"
            },
            {
                "title": "Отключены способы оплаты",
                "description": "Вы принимаете не все способы оплаты. Это уменьшает количество доступных заказов.",
                "action_url": "/driver/settings/payment"
            }
        ]
        
        # В реальном приложении здесь должна быть логика проверки ограничений для конкретного водителя
        # Если ограничений нет, передаем пустой список
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver,
            "limitations": limitations
        }
        
        return templates.TemplateResponse("driver/diagnostics/3.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы ограничений: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/board/1", response_class=HTMLResponse, name="driver_board")
async def driver_board_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница с полезными советами для водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/board/1.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы полезных советов: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/board/2", response_class=HTMLResponse, name="driver_board_start")
async def driver_board_start_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница 'С чего начать' в разделе полезных советов для водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/board/2.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы 'С чего начать': {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/board/3", response_class=HTMLResponse, name="driver_board_safety")
async def driver_board_safety_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница 'Безопасность' в разделе полезных советов для водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            return RedirectResponse(url="/driver/auth/step1")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            return RedirectResponse(url="/driver/survey/1")
        
        # Формируем данные для шаблона
        template_data = {
            "request": request,
            "user": user,
            "driver": driver
        }
        
        return templates.TemplateResponse("driver/board/3.html", template_data)
        
    except jose.jwt.JWTError:
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы 'Безопасность': {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/photocontrol/1", response_class=HTMLResponse, name="driver_photocontrol")
async def driver_photocontrol_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница фотоконтроля для водителя"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        print(f"Декодирование токена: {token[:20]}...")
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        print(f"Токен декодирован, user_id={user_id}")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            print(f"Пользователь с id={user_id} не найден, перенаправление на страницу авторизации")
            return RedirectResponse(url="/driver/auth/step1")
        
        print(f"Найден пользователь: id={user.id}, first_name={user.first_name}, driver_id={user.driver_id}")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            print("Водитель не найден, перенаправление на анкету")
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            print(f"Водитель с id={user.driver_id} не найден, перенаправление на анкету")
            return RedirectResponse(url="/driver/survey/1")
        
        print(f"Найден водитель: id={driver.id}, name={driver.full_name}")
        
        # Получаем информацию о статусе верификации 
        verification = db.query(models.DriverVerification).filter(
            models.DriverVerification.driver_id == driver.id,
            models.DriverVerification.verification_type == "photo_control"
        ).first()
        
        return templates.TemplateResponse(
            "driver/photocontrol/1.html",
            {
                "request": request,
                "user": user,
                "driver": driver,
                "verification": verification
            }
        )
    except jose.jwt.JWTError as e:
        print(f"Ошибка проверки JWT: {str(e)}")
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы фотоконтроля: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/photocontrol/upload", response_class=HTMLResponse, name="driver_photocontrol_upload")
async def driver_photocontrol_upload_page(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """Страница загрузки фотографий для фотоконтроля"""
    if not token:
        print("Токен отсутствует, перенаправление на страницу авторизации")
        return RedirectResponse(url="/driver/auth/step1")
    
    try:
        # Декодируем токен и получаем данные пользователя
        print(f"Декодирование токена: {token[:20]}...")
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        print(f"Токен декодирован, user_id={user_id}")
        
        # Получаем пользователя из БД
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user:
            print(f"Пользователь с id={user_id} не найден, перенаправление на страницу авторизации")
            return RedirectResponse(url="/driver/auth/step1")
        
        print(f"Найден пользователь: id={user.id}, first_name={user.first_name}, driver_id={user.driver_id}")
        
        # Проверяем связан ли пользователь с водителем
        if not user.driver_id:
            print("Водитель не найден, перенаправление на анкету")
            return RedirectResponse(url="/driver/survey/1")
        
        # Получаем данные водителя
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        if not driver:
            print(f"Водитель с id={user.driver_id} не найден, перенаправление на анкету")
            return RedirectResponse(url="/driver/survey/1")
        
        print(f"Найден водитель: id={driver.id}, name={driver.full_name}")
        
        return templates.TemplateResponse(
            "driver/photocontrol/upload.html",
            {
                "request": request,
                "user": user,
                "driver": driver
            }
        )
    except jose.jwt.JWTError as e:
        print(f"Ошибка проверки JWT: {str(e)}")
        return RedirectResponse(url="/driver/auth/step1")
    except Exception as e:
        print(f"Ошибка при загрузке страницы загрузки фотографий: {str(e)}")
        return HTMLResponse(content=f"Произошла ошибка: {str(e)}", status_code=500)

@app.get("/driver/logout", response_class=RedirectResponse, name="driver_logout")
async def driver_logout(response: Response):
    """Выход из аккаунта водителя. Удаляет токен из куки."""
    redirect = RedirectResponse(url="/driver/auth/step1")
    redirect.delete_cookie(key="token")
    return redirect

@app.post("/api/mobile/driver/register")
async def mobile_driver_register(
    request: Request, 
    full_name: str = Form(...), 
    phone: str = Form(...),
    city: str = Form(...),
    email: str = Form(...),
    driver_license_number: str = Form(...),
    driver_license_issue_date: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    """Регистрация водителя через мобильное приложение - первый шаг"""
    try:
        # Проверяем, не зарегистрирован ли уже такой номер
        existing_driver = db.query(models.Driver).filter(models.Driver.phone == phone).first()
        if existing_driver:
            return JSONResponse(
                status_code=400, 
                content={"detail": "Водитель с таким номером телефона уже зарегистрирован"}
            )
        
        # Преобразуем строку даты в объект даты
        license_issue_date = None
        if driver_license_issue_date:
            try:
                # Предполагаем формат даты DD.MM.YYYY
                day, month, year = driver_license_issue_date.split('.')
                license_issue_date = date(int(year), int(month), int(day))
            except ValueError:
                # Если формат неверный, используем текущую дату
                license_issue_date = date.today()
        
        # Создаем базовый словарь с данными водителя
        driver_data = {
            "full_name": full_name,
            "phone": phone,
            "city": city,
            "email": email,
            "driver_license_number": driver_license_number,
            "driver_license_issue_date": license_issue_date,
            "password": hash_password(password),
            "status": "pending",
        }
        
        # Безопасно добавляем новые поля, если они поддерживаются моделью
        try:
            # Проверяем, поддерживает ли модель Driver новые поля
            if hasattr(models.Driver, "is_mobile_registered"):
                driver_data["is_mobile_registered"] = True
            
            if hasattr(models.Driver, "registration_date"):
                # Используем переменную datetime из импорта в начале функции
                driver_data["registration_date"] = datetime.now()
                print(f"Добавлено поле registration_date = {datetime.now()}")
        except Exception as e:
            print(f"Предупреждение: Не удалось установить новые поля: {str(e)}")
        
        # Создаем объект водителя
        new_driver = models.Driver(**driver_data)
        
        db.add(new_driver)
        db.commit()
        db.refresh(new_driver)
        
        # Создаем токен для водителя
        token = create_driver_token(new_driver.id)
        
        # Возвращаем ID и токен нового водителя
        return {
            "id": new_driver.id,
            "token": token
        }
        
    except Exception as e:
        import traceback
        print(f"Ошибка при регистрации водителя: {str(e)}")
        print(traceback.format_exc())
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Ошибка при регистрации: {str(e)}"}
        )

@app.post("/api/driver/upload-photos", response_model=dict)
async def upload_driver_photos(
    request: Request,
    db: Session = Depends(get_db),
    passport_front: Optional[UploadFile] = File(None),
    passport_back: Optional[UploadFile] = File(None),
    license_front: Optional[UploadFile] = File(None),
    license_back: Optional[UploadFile] = File(None),
    car_front: Optional[UploadFile] = File(None),
    car_back: Optional[UploadFile] = File(None),
    car_right: Optional[UploadFile] = File(None),
    car_left: Optional[UploadFile] = File(None),
    interior_front: Optional[UploadFile] = File(None),
    interior_back: Optional[UploadFile] = File(None),
):
    """API для загрузки фотографий водителя и автомобиля"""
    try:
        # Получаем token из cookie
        token = request.cookies.get("token")
        if not token:
            return {"success": False, "detail": "Не авторизован"}
        
        # Декодируем токен
        payload = jose.jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        
        # Получаем пользователя и связанного водителя
        user = db.query(models.DriverUser).filter(models.DriverUser.id == user_id).first()
        if not user or not user.driver_id:
            return {"success": False, "detail": "Водитель не найден"}
        
        driver_id = user.driver_id
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return {"success": False, "detail": "Данные водителя не найдены"}
        
        # Проверяем, есть ли уже запись верификации в статусе "pending"
        existing_verification = db.query(models.DriverVerification).filter(
            models.DriverVerification.driver_id == driver_id,
            models.DriverVerification.verification_type == "photo_control",
            models.DriverVerification.status == "pending"
        ).first()
        
        if existing_verification:
            return {
                "success": False, 
                "detail": "Фотографии уже загружены и ожидают проверки. Пожалуйста, дождитесь решения администратора."
            }
        
        # Создаем папки для сохранения фотографий
        driver_photos_dir = Path(f"uploads/drivers/{driver_id}")
        driver_photos_dir.mkdir(parents=True, exist_ok=True)
        
        car_photos_dir = Path(f"uploads/cars/{driver_id}")
        car_photos_dir.mkdir(parents=True, exist_ok=True)
        
        # Функция для сохранения файла
        async def save_file(file: UploadFile, filepath: Path):
            if file:
                content = await file.read()
                with open(filepath, "wb") as f:
                    f.write(content)
                return str(filepath)
            return None
        
        # Сохраняем фотографии документов и обновляем атрибуты водителя
        if passport_front:
            passport_front_path = await save_file(passport_front, driver_photos_dir / "passport_front.jpg")
            driver.passport_front_path = f"/uploads/drivers/{driver_id}/passport_front.jpg"
        
        if passport_back:
            passport_back_path = await save_file(passport_back, driver_photos_dir / "passport_back.jpg")
            driver.passport_back_path = f"/uploads/drivers/{driver_id}/passport_back.jpg"
        
        if license_front:
            license_front_path = await save_file(license_front, driver_photos_dir / "license_front.jpg")
            driver.license_front_path = f"/uploads/drivers/{driver_id}/license_front.jpg"
        
        if license_back:
            license_back_path = await save_file(license_back, driver_photos_dir / "license_back.jpg")
            driver.license_back_path = f"/uploads/drivers/{driver_id}/license_back.jpg"
        
        # Сохраняем фотографии автомобиля
        car_photos = {}
        if car_front:
            car_photos["photo_front"] = f"/uploads/cars/{driver_id}/front.jpg"
            await save_file(car_front, car_photos_dir / "front.jpg")
        
        if car_back:
            car_photos["photo_rear"] = f"/uploads/cars/{driver_id}/back.jpg"
            await save_file(car_back, car_photos_dir / "back.jpg")
        
        if car_right:
            car_photos["photo_right"] = f"/uploads/cars/{driver_id}/right.jpg"
            await save_file(car_right, car_photos_dir / "right.jpg")
        
        if car_left:
            car_photos["photo_left"] = f"/uploads/cars/{driver_id}/left.jpg"
            await save_file(car_left, car_photos_dir / "left.jpg")
        
        if interior_front:
            car_photos["photo_interior_front"] = f"/uploads/cars/{driver_id}/interior_front.jpg"
            await save_file(interior_front, car_photos_dir / "interior_front.jpg")
        
        if interior_back:
            car_photos["photo_interior_rear"] = f"/uploads/cars/{driver_id}/interior_back.jpg"
            await save_file(interior_back, car_photos_dir / "interior_back.jpg")
        
        # Получаем или создаем машину водителя
        car = db.query(models.Car).filter(models.Car.driver_id == driver_id).first()
        if car:
            # Обновляем фотографии машины
            for field, value in car_photos.items():
                if hasattr(car, field):
                    setattr(car, field, value)
        else:
            # Проверяем, есть ли DriverCar
            driver_car = db.query(models.DriverCar).filter(models.DriverCar.driver_id == driver_id).first()
            if driver_car:
                # Обновляем фотографии DriverCar
                if car_front and hasattr(driver_car, "front_photo"):
                    driver_car.front_photo = f"/uploads/cars/{driver_id}/front.jpg"
                if car_back and hasattr(driver_car, "back_photo"):
                    driver_car.back_photo = f"/uploads/cars/{driver_id}/back.jpg"
                if car_right and hasattr(driver_car, "right_photo"):
                    driver_car.right_photo = f"/uploads/cars/{driver_id}/right.jpg"
                if car_left and hasattr(driver_car, "left_photo"):
                    driver_car.left_photo = f"/uploads/cars/{driver_id}/left.jpg"
                if interior_front and hasattr(driver_car, "interior_front_photo"):
                    driver_car.interior_front_photo = f"/uploads/cars/{driver_id}/interior_front.jpg"
                if interior_back and hasattr(driver_car, "interior_back_photo"):
                    driver_car.interior_back_photo = f"/uploads/cars/{driver_id}/interior_back.jpg"
        
        # Создаем запись в DriverVerification
        verification = models.DriverVerification(
            driver_id=driver_id,
            status="pending",
            verification_type="photo_control",
            comment="Ожидает проверки фотографий",
            created_at=datetime.now()
        )
        db.add(verification)
        
        # Сохраняем изменения в БД
        db.commit()
        
        return {
            "success": True, 
            "detail": "Фотографии успешно загружены. Они будут проверены администратором.",
            "driver_id": driver_id
        }
    
    except jose.jwt.JWTError as e:
        return {"success": False, "detail": f"Ошибка аутентификации: {str(e)}"}
    except Exception as e:
        import traceback
        print(f"Ошибка при загрузке фотографий: {str(e)}")
        print(traceback.format_exc())
        db.rollback()
        return {"success": False, "detail": f"Ошибка сервера: {str(e)}"}

@app.post("/api/drivers/{driver_id}/verify-photo", response_class=JSONResponse)
async def verify_driver_photo(
    driver_id: int, 
    request: Request, 
    db: Session = Depends(get_db)
):
    """API для верификации отдельной фотографии водителя"""
    try:
        # Получаем данные запроса
        data = await request.json()
        photo_type = data.get("photo_type")
        status = data.get("status")
        
        if not photo_type or not status or status not in ["accepted", "rejected", "pending"]:
            return JSONResponse(
                status_code=400, 
                content={"success": False, "detail": "Недопустимые параметры запроса"}
            )
        
        # Получаем водителя
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            return JSONResponse(
                status_code=404, 
                content={"success": False, "detail": "Водитель не найден"}
            )
        
        # Проверяем существование фотографии
        photo_exists = False
        
        # Проверка для документов водителя
        if photo_type in ["passport_front", "passport_back", "license_front", "license_back"]:
            path_field = f"{photo_type}_path"
            if hasattr(driver, path_field) and getattr(driver, path_field):
                photo_exists = True
        
        # Проверка для фотографий автомобиля
        else:
            car = db.query(models.Car).filter(models.Car.driver_id == driver_id).first()
            if car:
                car_photo_map = {
                    "car_front": "photo_front",
                    "car_back": "photo_rear",
                    "car_right": "photo_right",
                    "car_left": "photo_left",
                    "car_interior_front": "photo_interior_front",
                    "car_interior_back": "photo_interior_rear"
                }
                
                if photo_type in car_photo_map and hasattr(car, car_photo_map[photo_type]) and getattr(car, car_photo_map[photo_type]):
                    photo_exists = True
        
        if not photo_exists:
            return JSONResponse(
                status_code=404, 
                content={"success": False, "detail": "Фотография не найдена"}
            )
        
        # Получаем или создаем запись о верификации фотографии
        verification = db.query(models.DriverVerification).filter(
            models.DriverVerification.driver_id == driver_id,
            models.DriverVerification.verification_type == f"photo_{photo_type}"
        ).first()
        
        if not verification:
            verification = models.DriverVerification(
                driver_id=driver_id,
                status=status,
                verification_type=f"photo_{photo_type}",
                comment=f"Фотография {photo_type} проверена",
                created_at=datetime.now(),
                verified_at=datetime.now()
            )
            db.add(verification)
        else:
            verification.status = status
            verification.verified_at = datetime.now()
        
        # Если все фотографии проверены и одобрены, меняем статус водителя
        if status == "accepted":
            all_verifications = db.query(models.DriverVerification).filter(
                models.DriverVerification.driver_id == driver_id,
                models.DriverVerification.verification_type.like("photo_%")
            ).all()
            
            # Проверяем, есть ли хотя бы одна верификация для каждого типа фотографий
            required_photos = [
                "photo_passport_front", "photo_passport_back", 
                "photo_license_front", "photo_license_back"
            ]
            
            all_approved = True
            for req_photo in required_photos:
                found = False
                for v in all_verifications:
                    if v.verification_type == req_photo and v.status == "accepted":
                        found = True
                        break
                if not found:
                    all_approved = False
                    break
            
            # Если все обязательные фотографии одобрены, меняем статус водителя
            if all_approved:
                driver.status = "accepted"
        
        db.commit()
        
        return {"success": True}
    except Exception as e:
        import traceback
        print(f"Ошибка при верификации фотографии: {str(e)}")
        print(traceback.format_exc())
        db.rollback()
        return JSONResponse(
            status_code=500, 
            content={"success": False, "detail": f"Ошибка сервера: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 