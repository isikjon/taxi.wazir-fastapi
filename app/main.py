import logging
import sys
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
from sqlalchemy import func, or_, and_
from sqlalchemy.exc import IntegrityError
import jose.jwt
import secrets
import uuid
from pathlib import Path
from math import ceil
from contextlib import asynccontextmanager
import hashlib
from geopy.distance import geodesic

# Настройка подробного логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

# Включить логирование SQL-запросов
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Импорт модулей проекта
from . import crud, models, schemas
from .database import engine, SessionLocal, get_db, Base
from .routers import drivers, cars, orders, messages
from .models import TokenResponse
from .api import twogis
from .config import settings

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

# Отладочная информация при запуске
print("🚀 FastAPI приложение запускается...")
print(f"📁 Текущая директория: {os.getcwd()}")
print(f"📁 Существует ли папка templates: {os.path.exists('app/templates')}")
print(f"📁 Существует ли папка user: {os.path.exists('app/templates/user')}")
print(f"📁 Существует ли папка settings: {os.path.exists('app/templates/user/settings')}")
print(f"📁 Существует ли файл 1.html: {os.path.exists('app/templates/user/settings/1.html')}")

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

# ВАЖНО: Определяем кастомные endpoints ДО подключения роутеров
# чтобы они имели приоритет над {order_id} роутами

# ЗАКОММЕНТИРОВАНО: Эти эндпоинты перенесены в роутер orders
# @app.get("/api/orders/test", response_class=JSONResponse)
# async def test_orders_api():
#     """Тестовый endpoint для проверки API orders"""
#     return JSONResponse(
#         status_code=200,
#         content={"success": True, "message": "API orders работает!"}
#     )

# ЗАКОММЕНТИРОВАНО: Этот эндпоинт перенесен в роутер orders с улучшенной логикой
# @app.post("/api/orders/complete-with-progress", response_class=JSONResponse) 
# async def complete_order_with_progress(request: Request, db: Session = Depends(get_db)):
#     """Завершение поездки с прогрессом"""
#     try:
#         data = await request.json()
#         order_id = data.get("order_id")
#         driver_id = data.get("driver_id")
#         completion_type = data.get("completion_type", "full")
#         
#         print(f"🏁 Завершение поездки: order_id={order_id}, driver_id={driver_id}, type={completion_type}")
#         
#         if not all([order_id, driver_id]):
#             return JSONResponse(
#                 status_code=400,
#                 content={"success": False, "error": "Не указаны order_id или driver_id"}
#             )
#         
#         # Находим заказ
#         order = db.query(models.Order).filter(
#             models.Order.id == order_id,
#             models.Order.driver_id == driver_id
#         ).first()
#         
#         if not order:
#             return JSONResponse(
#                 status_code=404,
#                 content={"success": False, "error": "Заказ не найден или не принадлежит водителю"}
#             )
#         
#         # Проверяем статус
#         if order.status in ["Завершен", "Отменен"]:
#             return JSONResponse(
#                 status_code=400,
#                 content={"success": False, "error": f"Заказ уже {order.status.lower()}"}
#             )
#         
#         # Получаем водителя
#         driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
#         if not driver:
#             return JSONResponse(
#                 status_code=404,
#                 content={"success": False, "error": "Водитель не найден"}
#             )
#         
#         # Рассчитываем оплату
#         actual_payment = order.price or 0.0
#         progress_percentage = 0.0 if completion_type == "partial" else 100.0
#         
#         # Обновляем заказ
#         order.status = "Завершен"
#         order.progress_percentage = progress_percentage
#         order.actual_price = actual_payment
#         order.completed_at = datetime.now()
#         
#         # Обновляем баланс водителя
#         driver.balance = (driver.balance or 0.0) + actual_payment
#         
#         # Создаем транзакцию
#         transaction = models.BalanceTransaction(
#             driver_id=int(driver_id),
#             amount=float(actual_payment),
#             type="deposit",
#             status="completed",
#             description=f"Оплата за заказ #{order.order_number}"
#         )
#         db.add(transaction)
#         
#         # Увеличиваем активность
#         driver.activity = min(100, (getattr(driver, 'activity', 50) or 50) + 2)
#         
#         # Сохраняем изменения
#         db.commit()
#         db.refresh(order)
#         db.refresh(driver)
#         
#         print(f"✅ Заказ #{order.order_number} завершен. Оплата: {actual_payment} сом")
#         
#         return JSONResponse(
#             status_code=200,
#             content={
#                 "success": True,
#                 "message": f"Заказ #{order.order_number} успешно завершен",
#                 "order_id": order.id,
#                 "progress_percentage": progress_percentage,
#                 "actual_payment": actual_payment,
#                 "driver_balance": driver.balance,
#                 "completion_type": completion_type
#             }
#         )
#         
#     except Exception as e:
#         print(f"❌ Ошибка завершения поездки: {str(e)}")
#         import traceback
#         print(f"❌ Полная ошибка: {traceback.format_exc()}")
#         db.rollback()
#         return JSONResponse(
#             status_code=500,
#             content={
#                 "success": False,
#                 "error": f"Ошибка завершения поездки: {str(e)}"
#             }
#         )

# Подключаем API роутеры
app.include_router(drivers.router, prefix="/api")
app.include_router(cars.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(twogis.router, prefix="/api")

# Простой тестовый endpoint
@app.get("/test")
async def test_endpoint():
    """Тестовый endpoint для проверки работы приложения"""
    return {"status": "OK", "message": "Приложение работает!"}

# Middleware для проверки авторизации
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Список исключенных путей, которые не требуют авторизации
        excluded_paths = [
            '/disp/login', 
            '/login', 
            '/static', 
            '/driver/', 
            '/api/driver/', 
            '/api/twogis/', 
            '/user/', 
            '/api/user/',
            '/api/user-orders/',  # Добавляем endpoint для создания заказов пользователем
            '/api/available-tariffs',  # Добавляем endpoint для тарифов
            '/api/orders/',  # Добавляем endpoints для заказов (включая complete-with-progress)
            '/test'  # Тестовый endpoint
        ]
        
        # Логирование для отладки
        logger.info(f"🔍 AuthMiddleware: проверяем путь {request.url.path}")
        
        # Проверяем, начинается ли путь с любого из исключенных путей
        is_excluded = any(request.url.path.startswith(path) for path in excluded_paths)
        
        # Подробное логирование для отладки
        if request.url.path.startswith('/api/orders/'):
            logger.info(f"🔍 AuthMiddleware: Это API orders запрос!")
            logger.info(f"🔍 AuthMiddleware: Точный путь: {request.url.path}")
            logger.info(f"🔍 AuthMiddleware: Метод: {request.method}")
        
        logger.info(f"🔍 AuthMiddleware: путь {'исключен' if is_excluded else 'НЕ исключен'}")
        
        # Если путь не исключен, проверяем наличие сессии
        if not is_excluded:
            session = request.cookies.get("session")
            logger.info(f"🔍 AuthMiddleware: сессия {'найдена' if session else 'НЕ найдена'}")
            if not session:
                logger.info(f"🔍 AuthMiddleware: перенаправляем на логин")
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

# Модель запроса для отмены заказа
class CancelOrderRequest(BaseModel):
    cancelled_by: str  # "client" или "driver"
    reason: Optional[str] = None

# Модель для обновления позиции водителя
class UpdateDriverLocationRequest(BaseModel):
    driver_id: int
    latitude: float
    longitude: float
    order_id: Optional[int] = None

# Модель для завершения заказа с прогрессом
class CompleteOrderRequest(BaseModel):
    order_id: int
    driver_id: int
    completion_type: str  # "full" или "partial"
    final_latitude: Optional[float] = None
    final_longitude: Optional[float] = None

# Функция для создания JWT токена
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jose.jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Функция для расчета расстояния между двумя точками в километрах
def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Рассчитывает расстояние между двумя точками в километрах"""
    if not all([lat1, lng1, lat2, lng2]):
        return 0.0
    
    try:
        point1 = (lat1, lng1)
        point2 = (lat2, lng2)
        distance = geodesic(point1, point2).kilometers
        return round(distance, 3)
    except Exception as e:
        logger.error(f"Ошибка расчета расстояния: {e}")
        return 0.0

# Функция для расчета прогресса выполнения заказа
def calculate_order_progress(order, current_lat: float, current_lng: float) -> dict:
    """Рассчитывает прогресс выполнения заказа"""
    
    if not all([order.origin_lat, order.origin_lng, order.destination_lat, order.destination_lng]):
        return {"progress": 0.0, "completed_distance": 0.0, "remaining_distance": 0.0}
    
    # Общее расстояние маршрута
    total_distance = order.total_distance
    if not total_distance:
        total_distance = calculate_distance(
            order.origin_lat, order.origin_lng,
            order.destination_lat, order.destination_lng
        )
        if total_distance == 0:
            return {"progress": 0.0, "completed_distance": 0.0, "remaining_distance": 0.0}
    
    # Расстояние от текущей позиции до пункта назначения
    remaining_distance = calculate_distance(
        current_lat, current_lng,
        order.destination_lat, order.destination_lng
    )
    
    # Пройденное расстояние
    completed_distance = max(0, total_distance - remaining_distance)
    
    # Процент выполнения (максимум 100%)
    progress_percentage = min(100.0, (completed_distance / total_distance) * 100) if total_distance > 0 else 0.0
    
    return {
        "progress": round(progress_percentage, 2),
        "completed_distance": round(completed_distance, 3),
        "remaining_distance": round(remaining_distance, 3),
        "total_distance": round(total_distance, 3)
    }

# Функция для расчета фактической оплаты с учетом прогресса
def calculate_actual_payment(base_price: float, progress_percentage: float, min_percentage: float = 10.0) -> float:
    """Рассчитывает фактическую оплату с учетом прогресса выполнения заказа"""
    if not base_price or base_price <= 0:
        return 0.0
    
    # Минимальная оплата (например, 10% от общей суммы)
    min_payment = base_price * (min_percentage / 100)
    
    # Оплата по прогрессу
    progress_payment = base_price * (progress_percentage / 100)
    
    # Возвращаем максимум между минимальной оплатой и оплатой по прогрессу
    actual_payment = max(min_payment, progress_payment)
    
    return round(actual_payment, 2)


@app.get("/driver/", response_class=HTMLResponse)
async def driver_main(request: Request):
    return RedirectResponse(url="/driver/profile", status_code=302)

@app.get("/driver/online", response_class=HTMLResponse)
async def driver_online(request: Request, driver_id: Optional[int] = Query(None)):
    """Страница 'На линии' для водителя"""
    if not driver_id:
        # Пытаемся получить driver_id из cookies или сессии
        token = request.cookies.get("token")
        if token:
            try:
                payload = jose.jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
                driver_id = payload.get("driver_id")
            except:
                pass
    
    if not driver_id:
        return RedirectResponse(url="/driver/profile", status_code=302)
    
    return templates.TemplateResponse("driver/online.html", {
        "request": request,
        "driver_id": driver_id,
        "google_api_key": settings.GOOGLE_MAPS_API
    })

@app.get("/driver/test-order", response_class=HTMLResponse)
async def driver_test_order(request: Request):
    """Страница тестового заказа для обучения водителей"""
    return templates.TemplateResponse("driver/test_order.html", {
        "request": request,
        "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API
    })

# Роуты для клиентской части
@app.get("/user/auth/1", response_class=HTMLResponse)
async def user_auth_step1(request: Request):
    """Страница ввода номера телефона для пользователя"""
    return templates.TemplateResponse("user/auth/1.html", {"request": request})

@app.get("/user/auth/step1", response_class=HTMLResponse)
async def user_auth_step1_alt(request: Request):
    """Альтернативный роут для совместимости"""
    return templates.TemplateResponse("user/auth/1.html", {"request": request})

@app.get("/user/auth/2", response_class=HTMLResponse)
async def user_auth_step2(request: Request, phone: Optional[str] = None):
    """Страница ввода кода из СМС для пользователя"""
    return templates.TemplateResponse("user/auth/2.html", {"request": request, "phone": phone})

@app.get("/user/auth/step2", response_class=HTMLResponse)
async def user_auth_step2_alt(request: Request, phone: Optional[str] = None):
    """Альтернативный роут для совместимости"""
    return templates.TemplateResponse("user/auth/2.html", {"request": request, "phone": phone})

@app.get("/user/auth/3", response_class=HTMLResponse)
async def user_auth_step3(request: Request):
    """Страница ввода имени и фамилии для пользователя"""
    return templates.TemplateResponse("user/auth/3.html", {"request": request})

@app.get("/user/auth/step3", response_class=HTMLResponse)
async def user_auth_step3_alt(request: Request):
    """Альтернативный роут для совместимости"""
    return templates.TemplateResponse("user/auth/3.html", {"request": request})

@app.get("/user/profile", response_class=HTMLResponse)
async def user_profile(request: Request):
    """Главная страница пользователя с картой"""
    print(f"🔍 Запрос на страницу профиля: {request.url}")
    print(f"📁 Путь к шаблону: user/main.html")
    try:
        response = templates.TemplateResponse("user/main.html", {
            "request": request,
            "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API
        })
        print(f"✅ Шаблон профиля успешно загружен")
        return response
    except Exception as e:
        print(f"❌ Ошибка при загрузке шаблона профиля: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки страницы: {e}")

@app.get("/user/main", response_class=HTMLResponse)
async def user_main(request: Request):
    """Главная страница пользователя с картой"""
    print(f"🔍 Запрос на страницу main: {request.url}")
    print(f"📁 Путь к шаблону: user/main.html")
    try:
        response = templates.TemplateResponse("user/main.html", {
            "request": request,
            "GOOGLE_MAPS_API_KEY": settings.GOOGLE_MAPS_API
        })
        print(f"✅ Шаблон main успешно загружен")
        return response
    except Exception as e:
        print(f"❌ Ошибка при загрузке шаблона main: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки страницы: {e}")

@app.get("/user/settings", response_class=HTMLResponse)
async def user_settings(request: Request):
    """Страница настроек пользователя"""
    print(f"🔍 Запрос на страницу настроек: {request.url}")
    print(f"📁 Путь к шаблону: user/settings/1.html")
    print(f"📂 Текущая директория: {os.getcwd()}")
    print(f"📁 Существует ли шаблон: {os.path.exists('app/templates/user/settings/1.html')}")
    print(f"📁 Все доступные роуты:")
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"  - {route.methods} {route.path}")
    
    try:
        response = templates.TemplateResponse("user/settings/1.html", {"request": request})
        print(f"✅ Шаблон успешно загружен")
        return response
    except Exception as e:
        print(f"❌ Ошибка при загрузке шаблона: {e}")
        print(f"📋 Тип ошибки: {type(e)}")
        print(f"📋 Детали ошибки: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки страницы: {e}")

@app.get("/user/payment", response_class=HTMLResponse)
async def user_payment(request: Request):
    """Страница способа оплаты пользователя"""
    print(f"🔍 Запрос на страницу оплаты: {request.url}")
    print(f"📁 Путь к шаблону: user/payment/1.html")
    try:
        response = templates.TemplateResponse("user/payment/1.html", {"request": request})
        print(f"✅ Шаблон оплаты успешно загружен")
        return response
    except Exception as e:
        print(f"❌ Ошибка при загрузке шаблона оплаты: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка загрузки страницы оплаты: {e}")

@app.get("/test-settings")
async def test_settings():
    """Тестовый роут для проверки работы FastAPI"""
    return {"message": "Тестовый роут работает!", "status": "ok"}

@app.get("/api/user/profile/{user_id}")
async def get_user_profile(user_id: int, db: Session = Depends(get_db)):
    """Получить профиль пользователя по ID"""
    try:
        user = crud.get_driver_user(db, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        return {
            "id": user.id,
            "phone": user.phone,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_verified": user.is_verified,
            "has_profile": user.first_name is not None and user.last_name is not None
        }
    except Exception as e:
        print(f"Ошибка при получении профиля пользователя {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка сервера")

# Маршруты для диспетчерской панели
@app.get("/", response_class=HTMLResponse)
async def root_redirect(request: Request):
    """Перенаправление с корня на клиентскую часть"""
    return RedirectResponse(url="/user/auth/1", status_code=303)

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
        "is_filtered": is_filtered,
        
        # API ключ 2GIS
        "twogis_api_key": settings.TWOGIS_API_KEY,
        "google_api_key": settings.GOOGLE_MAPS_API
    }
    
    return templates.TemplateResponse("disp/index.html", {"request": request, **template_data})

@app.get("/disp/analytics", response_class=HTMLResponse)
async def disp_analytics(request: Request, db: Session = Depends(get_db)):
    """Страница аналитики"""
    from datetime import datetime, timedelta
    from sqlalchemy import func
    
    # Получаем данные о водителях, машинах и заказах из БД
    all_drivers = crud.get_drivers(db)
    all_cars = crud.get_cars(db)
    all_orders = crud.get_orders(db, limit=10000)  # Получаем больше заказов для аналитики
    
    # Расчет суммарного баланса всех водителей
    total_balance = 0
    if all_drivers:
        for driver in all_drivers:
            total_balance += driver.balance if driver.balance else 0
    
    # Расчеты по времени
    now = datetime.now()
    last_7_days = now - timedelta(days=7)
    last_30_days = now - timedelta(days=30)
    last_year = now - timedelta(days=365)
    
    # 📊 АНАЛИТИКА ПОПОЛНЕНИЙ БАЛАНСА
    # Примерные данные (в реальном проекте будет таблица пополнений)
    balance_stats = {
        "last_7_days": f"{total_balance * 0.1:.0f}",  # 10% от общего за неделю
        "last_30_days": f"{total_balance * 0.4:.0f}",  # 40% от общего за месяц
        "last_year": f"{total_balance:.0f}",  # Весь баланс за год
        "max_amount": "15000",  # Максимальное пополнение
        "min_amount": "500"     # Минимальное пополнение
    }
    
    # 🚗 АНАЛИТИКА ЗАКАЗОВ
    orders_with_price = [order for order in all_orders if order.price and order.price > 0]
    
    # Фильтрация заказов по периодам
    orders_7_days = [o for o in orders_with_price if o.created_at >= last_7_days]
    orders_30_days = [o for o in orders_with_price if o.created_at >= last_30_days]
    orders_year = [o for o in orders_with_price if o.created_at >= last_year]
    
    # Расчеты для заказов за 30 дней (по умолчанию)
    earnings_30_days = sum(order.price for order in orders_30_days)
    count_30_days = len(orders_30_days)
    avg_order_30_days = earnings_30_days / count_30_days if count_30_days > 0 else 0
    
    # Максимальный и минимальный заказы
    max_order = max((order.price for order in orders_with_price), default=0)
    min_order = min((order.price for order in orders_with_price), default=0)
    
    orders_stats = {
        "earnings_30_days": f"{earnings_30_days:.0f}",
        "count_30_days": str(count_30_days),
        "avg_order": f"{avg_order_30_days:.0f}",
        "max_order": f"{max_order:.0f}",
        "min_order": f"{min_order:.0f}",
        
        # Дополнительные данные для других периодов
        "earnings_7_days": f"{sum(order.price for order in orders_7_days):.0f}",
        "count_7_days": str(len(orders_7_days)),
        "earnings_year": f"{sum(order.price for order in orders_year):.0f}",
        "count_year": str(len(orders_year)),
        "earnings_all": f"{sum(order.price for order in orders_with_price):.0f}",
        "count_all": str(len(orders_with_price)),
        
        # Данные для пополнений
        "count_30_days": "12",  # Количество пополнений за месяц
        "avg_amount": f"{total_balance * 0.4 / 12:.0f}" if total_balance > 0 else "0"
    }
    
    # Формируем данные для диаграмм
    analytics_data = {
        "current_page": "analytics",
        "balance": f"{total_balance:.0f}",
        
        # Количество водителей и машин для диаграмм
        "total_drivers": len(all_drivers),
        "total_cars": len(all_cars),
        
        # 💰 Новые данные пополнений
        "balance_stats": balance_stats,
        
        # 🚗 Новые данные заказов  
        "orders_stats": orders_stats,
        
        # Данные для старых диаграмм (оставляем для совместимости)
        "total_orders": len(all_orders),
        "completed_orders": len([o for o in all_orders if o.status == "Завершен"]),
        "cancelled_orders": len([o for o in all_orders if o.status == "Отменен"]),
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

@app.get("/api/analytics/orders/{period}")
async def get_orders_analytics(period: str, db: Session = Depends(get_db)):
    """API для получения аналитики заказов за определенный период"""
    from datetime import datetime, timedelta
    
    all_orders = crud.get_orders(db, limit=10000)
    orders_with_price = [order for order in all_orders if order.price and order.price > 0]
    
    now = datetime.now()
    
    # Определяем период фильтрации
    if period == "7":
        filtered_orders = [o for o in orders_with_price if o.created_at >= now - timedelta(days=7)]
    elif period == "30":
        filtered_orders = [o for o in orders_with_price if o.created_at >= now - timedelta(days=30)]
    elif period == "365":
        filtered_orders = [o for o in orders_with_price if o.created_at >= now - timedelta(days=365)]
    else:  # "all"
        filtered_orders = orders_with_price
    
    # Расчеты
    total_earnings = sum(order.price for order in filtered_orders)
    total_count = len(filtered_orders)
    avg_order = total_earnings / total_count if total_count > 0 else 0
    
    return {
        "earnings": f"{total_earnings:.0f}",
        "count": str(total_count),
        "avg": f"{avg_order:.0f}"
    }

@app.get("/api/analytics/balance/{period}")
async def get_balance_analytics(period: str, db: Session = Depends(get_db)):
    """API для получения аналитики пополнений за определенный период"""
    from datetime import datetime, timedelta
    
    all_drivers = crud.get_drivers(db)
    total_balance = sum(driver.balance for driver in all_drivers if driver.balance)
    
    # Примерные данные (в реальном проекте будет таблица пополнений)
    mock_balance_data = {
        "7": {"total": f"{total_balance * 0.1:.0f}", "count": "3", "max": "8000", "avg": f"{total_balance * 0.1 / 3:.0f}"},
        "30": {"total": f"{total_balance * 0.4:.0f}", "count": "12", "max": "15000", "avg": f"{total_balance * 0.4 / 12:.0f}"},
        "365": {"total": f"{total_balance:.0f}", "count": "45", "max": "25000", "avg": f"{total_balance / 45:.0f}"},
        "all": {"total": f"{total_balance * 1.2:.0f}", "count": "68", "max": "30000", "avg": f"{total_balance * 1.2 / 68:.0f}"}
    }
    
    data = mock_balance_data.get(period, mock_balance_data["30"])
    return {
        "total": data["total"],
        "count": data["count"],
        "max": data["max"],
        "avg": data["avg"]
    }

@app.get("/api/analytics/balance-chart/{period}")
async def get_balance_chart_data(period: str):
    """API для получения данных графика пополнений"""
    
    if period == "7":
        return {
            "labels": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
            "data": [1200, 800, 0, 1500, 2200, 1800, 900]
        }
    elif period == "30":
        return {
            "labels": ["1", "5", "10", "15", "20", "25", "30"],
            "data": [3000, 5000, 2000, 8000, 12000, 7000, 4500]
        }
    elif period == "365":
        return {
            "labels": ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"],
            "data": [15000, 23000, 18000, 32000, 28000, 35000, 42000, 38000, 31000, 27000, 22000, 19000]
        }
    else:  # all
        return {
            "labels": ["2022", "2023", "2024", "2025"],
            "data": [180000, 250000, 320000, 85000]
        }

@app.get("/api/analytics/orders-chart/{period}")
async def get_orders_chart_data(period: str, db: Session = Depends(get_db)):
    """API для получения данных графика заказов"""
    from datetime import datetime, timedelta
    
    if period == "7":
        return {
            "labels": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
            "data": [18000, 22000, 19000, 25000, 32000, 38000, 28000]
        }
    elif period == "30":
        return {
            "labels": ["1-5", "6-10", "11-15", "16-20", "21-25", "26-30"],
            "data": [95000, 112000, 87000, 134000, 156000, 128000]
        }
    elif period == "365":
        return {
            "labels": ["Янв", "Фев", "Мар", "Апр", "Май", "Июн", "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"],
            "data": [320000, 385000, 298000, 456000, 512000, 478000, 523000, 489000, 445000, 398000, 356000, 412000]
        }
    else:  # all
        return {
            "labels": ["2022", "2023", "2024", "2025"],
            "data": [2800000, 3650000, 4250000, 1200000]
        }

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
            (status == 'занят' and getattr(d, 'is_busy', False)) or
            (status == 'свободен' and not getattr(d, 'is_busy', False))
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
    available_drivers = len([d for d in filtered_drivers if not getattr(d, 'is_busy', False)])
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
            "search": search if search else "",
            "status": status if status else "",
            "state": state if state else ""
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
        
        # Получаем документы водителя
        driver_docs = db.query(models.DriverDocuments).filter(
            models.DriverDocuments.driver_id == driver_id
        ).first()
        
        print(f"🔍 get_driver_details для водителя {driver_id}")
        print(f"📋 DriverDocuments найдены: {driver_docs is not None}")
        if driver_docs:
            print(f"  passport_front: {driver_docs.passport_front}")
            print(f"  passport_back: {driver_docs.passport_back}")
            print(f"  license_front: {driver_docs.license_front}")
            print(f"  license_back: {driver_docs.license_back}")
            print(f"  driver_with_license: {driver_docs.driver_with_license}")
        
        # Получаем последнюю верификацию
        verification = db.query(models.DriverVerification).filter(
            models.DriverVerification.driver_id == driver_id,
            models.DriverVerification.verification_type == "photo_control"
        ).order_by(models.DriverVerification.created_at.desc()).first()
        
        print(f"🔍 Верификация найдена: {verification.status if verification else 'None'}")
        
        # Формируем пути к фотографиям
        photo_paths = {
            "passport_front": driver_docs.passport_front if driver_docs and driver_docs.passport_front else None,
            "passport_back": driver_docs.passport_back if driver_docs and driver_docs.passport_back else None,
            "license_front": driver_docs.license_front if driver_docs and driver_docs.license_front else None,
            "license_back": driver_docs.license_back if driver_docs and driver_docs.license_back else None,
            "driver_with_license": driver_docs.driver_with_license if driver_docs and driver_docs.driver_with_license else None
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
            "is_disp_created": is_disp_created,
            "verification": {
                "status": verification.status if verification else None,
                "comment": verification.comment if verification else None,
                "created_at": verification.created_at.isoformat() if verification and verification.created_at else None,
                "verified_at": verification.verified_at.isoformat() if verification and verification.verified_at else None
            }
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
        
        print(f"📤 Возвращаем данные photos: {driver_data['photos']}")
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
    logger.info("🚀 Запрос страницы создания нового заказа")
    try:
        # Упрощенная обработка данных для избежания ошибок
        # 1. Базовые значения по умолчанию
        # Генерируем случайные номера заказа (9 цифр) и путевого листа (8 цифр)
        order_number = f"{random.randint(100000000, 999999999)}"
        route_number = f"{random.randint(10000000, 99999999)}"
        
        logger.info(f"📝 Сгенерированы номера: заказ {order_number}, путевой лист {route_number}")
        logger.info(f"🔑 API ключ 2GIS настроен: {'Да' if settings.TWOGIS_API_KEY else 'Нет'}")
        logger.info(f"🔑 Google Maps API ключ: {'Да' if settings.GOOGLE_MAPS_API else 'Нет'}")
        logger.info(f"🔑 Google ключ (первые 10 символов): {settings.GOOGLE_MAPS_API[:10] if settings.GOOGLE_MAPS_API else 'НЕТ'}")
        
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
            "route_number": route_number,
            "twogis_api_key": settings.TWOGIS_API_KEY,
            "google_api_key": settings.GOOGLE_MAPS_API
        }
        
        logger.info("📤 API ключ передан в шаблон")
        
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
        logger.info("✅ Возвращаем шаблон new_order.html с данными")
        return templates.TemplateResponse("disp/new_order.html", template_data)
    
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в маршруте disp_new_order: {e}")
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
            "route_number": f"{random.randint(10000000, 99999999)}",
            "twogis_api_key": settings.TWOGIS_API_KEY,
            "google_api_key": settings.GOOGLE_MAPS_API
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
    print(f"🔍 Получение фотографий для водителя {driver_id}")
    
    driver = crud.get_driver(db, driver_id=driver_id)
    if not driver:
        return JSONResponse(status_code=404, content={"detail": "Водитель не найден"})
    
    # Получаем документы водителя
    driver_docs = db.query(models.DriverDocuments).filter(
        models.DriverDocuments.driver_id == driver_id
    ).first()
    
    print(f"📋 DriverDocuments найдены: {driver_docs is not None}")
    if driver_docs:
        print(f"passport_front: {driver_docs.passport_front}")
        print(f"passport_back: {driver_docs.passport_back}")
        print(f"license_front: {driver_docs.license_front}")
        print(f"license_back: {driver_docs.license_back}")
        print(f"driver_with_license: {driver_docs.driver_with_license}")
    
    # Получаем автомобиль водителя
    car = driver.cars[0] if driver.cars else None
    print(f"🚗 Car найден: {car is not None}")
    
    # Формируем пути к фотографиям
    photo_paths = {
        "passport_front": driver_docs.passport_front if driver_docs and driver_docs.passport_front else None,
        "passport_back": driver_docs.passport_back if driver_docs and driver_docs.passport_back else None,
        "license_front": driver_docs.license_front if driver_docs and driver_docs.license_front else None,
        "license_back": driver_docs.license_back if driver_docs and driver_docs.license_back else None,
        "driver_with_license": driver_docs.driver_with_license if driver_docs and driver_docs.driver_with_license else None,
        "car_front": car.photo_front if car and car.photo_front else None,
        "car_back": car.photo_rear if car and car.photo_rear else None,
        "car_right": car.photo_right if car and car.photo_right else None,
        "car_left": car.photo_left if car and car.photo_left else None,
        "car_interior_front": car.photo_interior_front if car and car.photo_interior_front else None,
        "car_interior_back": car.photo_interior_rear if car and car.photo_interior_rear else None,
    }
    
    print(f"📸 Возвращаемые пути: {photo_paths}")
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
    """ВРЕМЕННО: Отключена логика авторизации - любой номер телефона перенаправляет на профиль 9961111111111"""
    
    # ВРЕМЕННО: Ищем пользователя с номером 9961111111111
    target_phone = "9961111111111"
    target_user = crud.get_driver_user_by_phone(db, target_phone)
    
    if not target_user:
        # Если пользователя нет, создаем его
        target_user = crud.create_driver_user(db, schemas.DriverUserCreate(phone=target_phone))
    
    # ВРЕМЕННО: Возвращаем успех для любого номера телефона
    return {"success": True, "message": "Временный режим: авторизация отключена", "target_user_id": target_user.id}

# ВРЕМЕННЫЙ endpoint для проверки пользователя 9961111111111
@app.get("/api/driver/check-target-user")
async def check_target_user(db: Session = Depends(get_db)):
    """ВРЕМЕННЫЙ: Проверка существования пользователя с номером 9961111111111"""
    target_phone = "9961111111111"
    target_user = crud.get_driver_user_by_phone(db, target_phone)
    
    if target_user:
        return {
            "exists": True,
            "user_id": target_user.id,
            "phone": target_user.phone,
            "driver_id": target_user.driver_id,
            "is_verified": target_user.is_verified
        }
    else:
        return {"exists": False, "message": "Пользователь не найден"}

# ВРЕМЕННЫЙ тестовый endpoint для проверки временного режима
@app.get("/api/driver/test-temp-mode")
async def test_temp_mode(db: Session = Depends(get_db)):
    """ВРЕМЕННЫЙ: Тестовый endpoint для проверки временного режима"""
    target_phone = "9961111111111"
    
    # Проверяем пользователя
    user = crud.get_driver_user_by_phone(db, target_phone)
    if not user:
        user = crud.create_driver_user(db, schemas.DriverUserCreate(phone=target_phone))
    
    # Проверяем водителя
    driver = None
    if user.driver_id:
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
    
    if not driver:
        driver = db.query(models.Driver).filter(models.Driver.phone == target_phone).first()
        if driver:
            user.driver_id = driver.id
            db.commit()
    
    return {
        "temp_mode": "enabled",
        "message": "Временный режим активен - авторизация отключена",
        "target_phone": target_phone,
        "user": {
            "id": user.id,
            "phone": user.phone,
            "driver_id": user.driver_id
        },
        "driver": {
            "id": driver.id if driver else None,
            "name": driver.full_name if driver else None,
            "phone": driver.phone if driver else None
        } if driver else None
    }


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
        "driver_id": driver_id if has_driver else None,
        "has_profile": True  # Для драйверов всегда True, так как они проходят полную регистрацию
    }
    print(f"Отправляем ответ: {response_data}")
    return response_data

@app.post("/api/driver/update-profile", response_class=JSONResponse)
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

# API роуты для клиентской части
@app.post("/api/user/login", response_model=dict)
async def user_login(request: DriverLoginRequest, db: Session = Depends(get_db)):
    """Отправка кода подтверждения на телефон пользователя"""
    # Форматируем номер телефона - удаляем все кроме цифр
    phone = ''.join(filter(str.isdigit, request.phone))
    print(f"API: Вход пользователя с телефоном: {phone}")
    
    # Проверяем, существует ли уже пользователь с таким номером
    user = crud.get_driver_user_by_phone(db, phone)
    
    # Если пользователя нет, создаем его
    if not user:
        print(f"API: Создаем нового пользователя с телефоном {phone}")
        user = crud.create_driver_user(db, schemas.DriverUserCreate(phone=phone))
        print(f"API: Пользователь создан с ID {user.id}")
    else:
        print(f"API: Найден существующий пользователь с ID {user.id}")
    
    # В реальном приложении здесь была бы отправка SMS
    # Для тестирования используем фиксированный код 1111
    verification_code = "1111"
    
    return {"success": True, "message": "Код подтверждения отправлен"}

@app.post("/api/user/verify-code", response_model=TokenResponse)
async def user_verify_code(request: VerifyCodeRequest, response: Response = None, db: Session = Depends(get_db)):
    """
    Проверка кода подтверждения и выдача JWT токена для пользователя.
    
    Возвращает:
    - access_token: JWT токен для аутентификации
    - token_type: Тип токена (bearer)
    - user_id: ID пользователя
    - has_profile: Флаг, указывающий, заполнил ли пользователь профиль
    """
    # Форматируем номер телефона - удаляем все кроме цифр
    raw_phone = request.phone
    phone = ''.join(filter(str.isdigit, request.phone))
    print(f"Верификация кода пользователя для телефона: {phone} (исходный: {raw_phone})")
    
    # Получаем пользователя по номеру телефона
    user = crud.get_driver_user_by_phone(db, phone)
    if not user:
        print(f"Пользователь с телефоном {phone} не найден")
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    print(f"Найден пользователь: id={user.id}, first_name={user.first_name}")
    
    # В тестовом режиме проверяем только на фиксированный код 1111
    if request.code != "1111":
        print(f"Неверный код: {request.code}, ожидается 1111")
        raise HTTPException(status_code=400, detail="Неверный код подтверждения")
    
    # Отмечаем пользователя как верифицированного
    user_update = schemas.DriverUserUpdate(is_verified=True)
    user = crud.update_driver_user(db, user.id, user_update)
    
    # Обновляем время последнего входа
    crud.update_last_login(db, user.id)
    
    # Получаем обновленные данные пользователя
    user = crud.get_driver_user(db, user.id)
    
    # Проверяем, заполнен ли профиль пользователя (имя и фамилия)
    has_profile = user.first_name is not None and user.last_name is not None
    print(f"Проверка наличия профиля: has_profile={has_profile}")
    print(f"Данные пользователя: id={user.id}, first_name='{user.first_name}', last_name='{user.last_name}'")
    
    # Создаем JWT токен
    access_token = create_access_token(
        data={"sub": str(user.id), "type": "user"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    # Возвращаем токен и информацию о пользователе
    response_data = TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        has_driver=False,  # Для клиентов всегда False
        driver_id=None,
        has_profile=has_profile
    )
    
    print(f"Отправляем ответ: {response_data}")
    return response_data

@app.post("/api/user/update-profile", response_model=dict)
async def user_update_profile(request: Request, db: Session = Depends(get_db)):
    """Обновление профиля пользователя (имя и фамилия)"""
    try:
        # Получаем данные из JSON body
        body = await request.json()
        user_id = body.get("user_id")
        first_name = body.get("first_name")
        last_name = body.get("last_name")
        
        print(f"Обновление профиля: user_id={user_id} (тип: {type(user_id)}), first_name='{first_name}', last_name='{last_name}'")
        
        # Убеждаемся, что user_id - это число
        try:
            user_id = int(user_id)
        except (ValueError, TypeError):
            print(f"Ошибка: user_id не является числом: {user_id}")
            raise HTTPException(status_code=400, detail="ID пользователя должен быть числом")
        
        if not first_name or not last_name:
            print(f"Ошибка валидации: user_id={user_id}, first_name='{first_name}', last_name='{last_name}'")
            raise HTTPException(status_code=400, detail="Имя и фамилия обязательны")
        
        # Получаем пользователя
        user = crud.get_driver_user(db, user_id)
        if not user:
            print(f"Пользователь с ID {user_id} не найден")
            raise HTTPException(status_code=404, detail="Пользователь не найден")
        
        print(f"Найден пользователь: id={user.id}, phone={user.phone}")
        
        # Обновляем профиль
        user_update = schemas.DriverUserUpdate(
            first_name=first_name,
            last_name=last_name
        )
        
        print(f"Создаем схему обновления: {user_update}")
        print(f"Тип схемы: {type(user_update)}")
        
        user = crud.update_driver_user(db, user.id, user_update)
        
        if user:
            print(f"Профиль успешно обновлен для пользователя {user.id}")
            print(f"Проверяем обновленные данные: first_name='{user.first_name}', last_name='{user.last_name}'")
            return {"success": True, "message": "Профиль пользователя обновлен успешно"}
        else:
            print(f"Ошибка: crud.update_driver_user вернул None")
            raise HTTPException(status_code=500, detail="Ошибка обновления профиля")
    except Exception as e:
        print(f"Ошибка при обновлении профиля пользователя: {str(e)}")
        logger.error(f"Ошибка при обновлении профиля пользователя: {str(e)}")
        raise HTTPException(status_code=500, detail="Внутренняя ошибка сервера")

@app.get("/api/user/{user_id}/frequent-addresses", response_model=dict)
async def get_user_frequent_addresses(user_id: int, db: Session = Depends(get_db)):
    """Получение частых адресов пользователя"""
    try:
        # Получаем завершенные заказы пользователя (если у нас есть таблица заказов для клиентов)
        # Пока вернем заглушку, так как у нас нет отдельной таблицы заказов для клиентов
        
        # В будущем здесь будет запрос к базе данных:
        # orders = db.query(UserOrder).filter(
        #     UserOrder.user_id == user_id,
        #     UserOrder.status == "Завершен"
        # ).limit(10).all()
        
        # Пока возвращаем пустой список для новых пользователей
        return {
            "success": True,
            "addresses": []
        }
    except Exception as e:
        logger.error(f"❌ Ошибка получения частых адресов для пользователя {user_id}: {e}")
        return {
            "success": False,
            "addresses": [],
            "error": str(e)
        }

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
    """ВРЕМЕННО: Страница профиля водителя - авторизация отключена"""
    
    # ВРЕМЕННО: Ищем пользователя с номером 9961111111111 (нормализованный)
    target_phone = "9961111111111"
    user = crud.get_driver_user_by_phone(db, target_phone)
    
    if not user:
        # Если пользователя нет, создаем его с нормализованным номером
        user = crud.create_driver_user(db, schemas.DriverUserCreate(phone=target_phone))
        print(f"Создан новый пользователь с номером {target_phone}, id={user.id}")
    
    print(f"Временный режим: используем пользователя id={user.id}, phone={user.phone}")
    
    # Получаем данные водителя
    driver = None
    if user.driver_id:
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        print(f"Найден водитель: id={driver.id if driver else 'None'}, name={driver.full_name if driver else 'None'}")
    
    if not driver:
        # Если водитель не найден, ищем по нормализованному номеру телефона в таблице drivers
        driver = db.query(models.Driver).filter(models.Driver.phone == target_phone).first()
        if driver:
            # Связываем пользователя с водителем
            user.driver_id = driver.id
            db.commit()
            print(f"Связали пользователя {user.id} с водителем {driver.id}")
        else:
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
    
    # Формируем имя водителя, используя данные пользователя или водителя
    driver_name = None
    if user.first_name and user.last_name:
        driver_name = f"{user.first_name} {user.last_name}"
    elif driver.full_name:
        driver_name = driver.full_name
    else:
        driver_name = "Водитель"
    
    template_data = {
        "request": request,
        "user": user,
        "driver": driver,
        "driver_id": str(driver.id),
        "current_date": current_date,
        "tariff": driver.tariff,
        "driver_name": driver_name,
        "car_info": car_info,
        "issues_count": issues_count  # Передаем количество проблем в шаблон
    }
    
    print(f"Временный режим: отрисовка профиля для водителя id={driver.id}")
    print(f"Данные пользователя: phone={user.phone}, first_name='{user.first_name}', last_name='{user.last_name}'")
    return templates.TemplateResponse("driver/profile/1.html", template_data)

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
async def get_driver_profile(driver_id: int, db: Session = Depends(get_db)):
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
        car = db.query(models.Car).filter(models.Car.driver_id == driver_id).first()
        car_data = None
        
        if car:
            car_data = {
                "brand": car.brand,
                "model": car.model,
                "number": car.license_plate,
                "sts": car.sts if hasattr(car, 'sts') else None
            }
        
        # Получаем документы водителя
        driver_docs = db.query(models.DriverDocuments).filter(
            models.DriverDocuments.driver_id == driver_id
        ).first()
        
        print(f"📋 Документы водителя для профиля: {driver_docs is not None}")
        if driver_docs:
            print(f"  passport_front: {driver_docs.passport_front}")
            print(f"  passport_back: {driver_docs.passport_back}")
            print(f"  license_front: {driver_docs.license_front}")
            print(f"  license_back: {driver_docs.license_back}")
        
        # Формируем пути к документам
        documents = {
            "passport_front": driver_docs.passport_front if driver_docs and driver_docs.passport_front else None,
            "passport_back": driver_docs.passport_back if driver_docs and driver_docs.passport_back else None,
            "license_front": driver_docs.license_front if driver_docs and driver_docs.license_front else None,
            "license_back": driver_docs.license_back if driver_docs and driver_docs.license_back else None,
            "driver_with_license": driver_docs.driver_with_license if driver_docs and driver_docs.driver_with_license else None
        }
        
        # Добавляем фото автомобиля в documents
        if car:
            documents.update({
                "car_front": car.photo_front,
                "car_back": car.photo_rear,
                "car_right": car.photo_right,
                "car_left": car.photo_left,
                "car_interior_front": car.photo_interior_front,
                "car_interior_back": car.photo_interior_rear
            })
        
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
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "id": driver.id,
                "full_name": driver.full_name,
                "phone": driver.phone,
                "car": car_data,
                "park": park_name,
                "rating": rating,
                "activity": activity,
                "balance": getattr(driver, 'balance', 0) or 0,
                "documents": documents
            }
        )
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
        
        # Получаем реальные заказы водителя за указанную дату
        orders = db.query(models.Order).filter(
            models.Order.driver_id == driver_id,
            models.Order.created_at >= day_start,
            models.Order.created_at < day_end
        ).all()
        
        # Подсчитываем статистику
        total_orders = len(orders)
        completed_orders = len([o for o in orders if o.status == "Завершен"])
        active_orders = len([o for o in orders if o.status in ["Выполняется", "Принят"]])
        cancelled_orders = len([o for o in orders if o.status in ["Отменен", "Отклонен водителем"]])
        total_earnings = sum(o.price for o in orders if o.status == "Завершен" and o.price)
        
        logger.info(f"📊 Статистика водителя {driver_id} за {date}: {total_orders} заказов, {total_earnings} сом")
        
        # Формируем детализацию заказов
        formatted_orders = []
        for order in orders:
            formatted_orders.append({
                "id": order.id,
                "order_number": order.order_number,
                "time": order.time or order.created_at.strftime("%H:%M") if order.created_at else "—",
                "origin": order.origin,
                "destination": order.destination,
                "status": order.status,
                "price": order.price or 0
            })
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "data": {
                    "driver_id": driver_id,
            "date": date,
                    "stats": {
                        "total_orders": total_orders,
                        "completed_orders": completed_orders,
                        "active_orders": active_orders,
                        "cancelled_orders": cancelled_orders,
                        "total_earnings": total_earnings
                    },
                    "orders": formatted_orders
                }
            }
        )
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
    """ВРЕМЕННО: Страница баланса и истории транзакций водителя - авторизация отключена"""
    
    # ВРЕМЕННО: Ищем пользователя с номером 9961111111111
    target_phone = "9961111111111"
    user = crud.get_driver_user_by_phone(db, target_phone)
    
    if not user:
        # Если пользователя нет, создаем его
        user = crud.create_driver_user(db, schemas.DriverUserCreate(phone=target_phone))
        print(f"Создан новый пользователь с номером {target_phone}, id={user.id}")
    
    print(f"Временный режим: используем пользователя id={user.id}, phone={user.phone}")
    
    # Получаем данные водителя
    driver = None
    if user.driver_id:
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        print(f"Найден водитель: id={driver.id if driver else 'None'}, name={driver.full_name if driver else 'None'}")
    
    if not driver:
        # Если водитель не найден, ищем по номеру телефона в таблице drivers
        driver = db.query(models.Driver).filter(models.Driver.phone == target_phone).first()
        if driver:
            # Связываем пользователя с водителем
            user.driver_id = driver.id
            db.commit()
            print(f"Связали пользователя {user.id} с водителем {driver.id}")
        else:
            print("Водитель не найден, перенаправление на анкету")
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
    
    # Формируем имя водителя, используя данные пользователя или водителя
    driver_name = None
    if user.first_name and user.last_name:
        driver_name = f"{user.first_name} {user.last_name}"
    elif driver.full_name:
        driver_name = driver.full_name
    else:
        driver_name = "Водитель"
    
    # Формируем данные для шаблона
    template_data = {
        "request": request,
        "user": user,
        "driver": driver,
        "balance": driver.balance,
        "balance_formatted": f"{driver.balance:.2f}",
        "transactions": transaction_list,
        "driver_name": driver_name,
        "driver_id": driver.id
    }
    
    print(f"Временный режим: отрисовка баланса для водителя id={driver.id}")
    print(f"Данные пользователя: phone={user.phone}, first_name='{user.first_name}', last_name='{user.last_name}'")
    return templates.TemplateResponse("driver/profile/balance.html", template_data)

@app.get("/driver/balance/top-up", response_class=HTMLResponse)
async def driver_balance_top_up(request: Request, db: Session = Depends(get_db), token: Optional[str] = Cookie(None)):
    """ВРЕМЕННО: Страница пополнения баланса водителя - авторизация отключена"""
    
    # ВРЕМЕННО: Ищем пользователя с номером 9961111111111
    target_phone = "9961111111111"
    user = crud.get_driver_user_by_phone(db, target_phone)
    
    if not user:
        # Если пользователя нет, создаем его
        user = crud.create_driver_user(db, schemas.DriverUserCreate(phone=target_phone))
        print(f"Создан новый пользователь с номером {target_phone}, id={user.id}")
    
    print(f"Временный режим: используем пользователя id={user.id}, phone={user.phone}")
    
    # Получаем данные водителя
    driver = None
    if user.driver_id:
        driver = db.query(models.Driver).filter(models.Driver.id == user.driver_id).first()
        print(f"Найден водитель: id={driver.id if driver else 'None'}, name={driver.full_name if driver else 'None'}")
    
    if not driver:
        # Если водитель не найден, ищем по номеру телефона в таблице drivers
        driver = db.query(models.Driver).filter(models.Driver.phone == target_phone).first()
        if driver:
            # Связываем пользователя с водителем
            user.driver_id = driver.id
            db.commit()
            print(f"Связали пользователя {user.id} с водителем {driver.id}")
        else:
            print("Водитель не найден, перенаправление на анкету")
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
    
    print(f"Временный режим: отрисовка пополнения баланса для водителя id={driver.id}")
    print(f"Данные пользователя: phone={user.phone}, first_name='{user.first_name}', last_name='{user.last_name}'")
    return templates.TemplateResponse("driver/profile/top-up.html", template_data)

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
        
        # Получаем документы водителя из таблицы DriverDocuments
        driver_docs = db.query(models.DriverDocuments).filter(
            models.DriverDocuments.driver_id == driver.id
        ).first()
        
        print(f"📋 Документы для водительского приложения: {driver_docs is not None}")
        if driver_docs:
            print(f"  passport_front: {driver_docs.passport_front}")
            print(f"  license_front: {driver_docs.license_front}")
        
        # Формируем пути к документам из БД
        docs_photos = {
            "passport_front": driver_docs.passport_front if driver_docs and driver_docs.passport_front else None,
            "passport_back": driver_docs.passport_back if driver_docs and driver_docs.passport_back else None,
            "license_front": driver_docs.license_front if driver_docs and driver_docs.license_front else None,
            "license_back": driver_docs.license_back if driver_docs and driver_docs.license_back else None,
            "driver_with_license": driver_docs.driver_with_license if driver_docs and driver_docs.driver_with_license else None
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
            with open("app/data/driver_data.json", "r", encoding="utf-8") as f:
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
        
        # Получаем информацию о статусе верификации (самую последнюю)
        verification = db.query(models.DriverVerification).filter(
            models.DriverVerification.driver_id == driver.id,
            models.DriverVerification.verification_type == "photo_control"
        ).order_by(models.DriverVerification.created_at.desc()).first()
        
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
    driver_with_license: Optional[UploadFile] = File(None),
    car_front: Optional[UploadFile] = File(None),
    car_back: Optional[UploadFile] = File(None),
    car_right: Optional[UploadFile] = File(None),
    car_left: Optional[UploadFile] = File(None),
    interior_front: Optional[UploadFile] = File(None),
    interior_back: Optional[UploadFile] = File(None),
):
    """API для загрузки фотографий водителя и автомобиля"""
    try:
        print(f"🚀 Начинаем загрузку фотографий")
        print(f"passport_front: {passport_front.filename if passport_front else 'None'}")
        print(f"passport_back: {passport_back.filename if passport_back else 'None'}")
        print(f"license_front: {license_front.filename if license_front else 'None'}")
        print(f"license_back: {license_back.filename if license_back else 'None'}")
        print(f"driver_with_license: {driver_with_license.filename if driver_with_license else 'None'}")
        
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
        
        # Проверяем текущий статус верификации
        existing_verification = db.query(models.DriverVerification).filter(
            models.DriverVerification.driver_id == driver_id,
            models.DriverVerification.verification_type == "photo_control"
        ).order_by(models.DriverVerification.created_at.desc()).first()
        
        # Блокируем повторную загрузку только если статус "pending"
        if existing_verification and existing_verification.status == "pending":
            return {
                "success": False, 
                "detail": "Фотографии уже загружены и ожидают проверки. Пожалуйста, дождитесь решения администратора."
            }
        
        # Если статус "rejected", то обновляем существующую запись, иначе создаем новую
        if existing_verification and existing_verification.status == "rejected":
            verification = existing_verification
            verification.status = "pending"
            verification.comment = "Повторная загрузка после отклонения"
            verification.created_at = datetime.now()
            verification.verified_at = None
        else:
            # Создаем новую запись в DriverVerification
            verification = models.DriverVerification(
                driver_id=driver_id,
                status="pending",
                verification_type="photo_control",
                comment="Ожидает проверки фотографий",
                created_at=datetime.now()
            )
            db.add(verification)
        
        # Создаем папки для сохранения фотографий
        driver_photos_dir = Path(f"uploads/drivers/{driver_id}")
        driver_photos_dir.mkdir(parents=True, exist_ok=True)
        
        car_photos_dir = Path(f"uploads/cars/{driver_id}")
        car_photos_dir.mkdir(parents=True, exist_ok=True)
        
        # Функция для сохранения файла
        async def save_file(file: UploadFile, filepath: Path):
            if file:
                print(f"💾 Сохраняем файл: {file.filename} -> {filepath}")
                content = await file.read()
                with open(filepath, "wb") as f:
                    f.write(content)
                print(f"✅ Файл сохранен: {filepath} ({len(content)} bytes)")
                return str(filepath)
            return None
        
        # Получаем или создаем запись документов для водителя
        driver_docs = db.query(models.DriverDocuments).filter(
            models.DriverDocuments.driver_id == driver_id
        ).first()
        
        if not driver_docs:
            print(f"📋 Создаем новую запись DriverDocuments для водителя {driver_id}")
            driver_docs = models.DriverDocuments(driver_id=driver_id)
            db.add(driver_docs)
            db.commit()
            db.refresh(driver_docs)
            print(f"✅ Создана запись DriverDocuments с ID: {driver_docs.id}")
        else:
            print(f"📋 Используем существующую запись DriverDocuments ID: {driver_docs.id}")
        
        # Сохраняем фотографии документов
        print(f"🔍 Сохранение документов для водителя {driver_id}")
        print(f"passport_front: {passport_front is not None}")
        print(f"passport_back: {passport_back is not None}")
        print(f"license_front: {license_front is not None}")
        print(f"license_back: {license_back is not None}")
        print(f"driver_with_license: {driver_with_license is not None}")
        
        if passport_front:
            await save_file(passport_front, driver_photos_dir / "passport_front.jpg")
            driver_docs.passport_front = f"/uploads/drivers/{driver_id}/passport_front.jpg"
            print(f"✅ Сохранен passport_front: {driver_docs.passport_front}")
        
        if passport_back:
            await save_file(passport_back, driver_photos_dir / "passport_back.jpg")
            driver_docs.passport_back = f"/uploads/drivers/{driver_id}/passport_back.jpg"
            print(f"✅ Сохранен passport_back: {driver_docs.passport_back}")
        
        if license_front:
            await save_file(license_front, driver_photos_dir / "license_front.jpg")
            driver_docs.license_front = f"/uploads/drivers/{driver_id}/license_front.jpg"
            print(f"✅ Сохранен license_front: {driver_docs.license_front}")
        
        if license_back:
            await save_file(license_back, driver_photos_dir / "license_back.jpg")
            driver_docs.license_back = f"/uploads/drivers/{driver_id}/license_back.jpg"
            print(f"✅ Сохранен license_back: {driver_docs.license_back}")
        
        if driver_with_license:
            await save_file(driver_with_license, driver_photos_dir / "driver_with_license.jpg")
            driver_docs.driver_with_license = f"/uploads/drivers/{driver_id}/driver_with_license.jpg"
            print(f"✅ Сохранен driver_with_license: {driver_docs.driver_with_license}")
        
        # Коммитим изменения документов
        print(f"💾 Коммит документов в БД...")
        db.commit()
        db.refresh(driver_docs)
        print(f"✅ Документы сохранены в БД")
        
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
        
        # Сохраняем изменения в БД
        print(f"💾 Финальный коммит всех изменений...")
        db.commit()
        
        # Проверяем что документы действительно сохранились
        saved_docs = db.query(models.DriverDocuments).filter(
            models.DriverDocuments.driver_id == driver_id
        ).first()
        print(f"🔍 Проверка сохранения:")
        if saved_docs:
            print(f"  passport_front: {saved_docs.passport_front}")
            print(f"  passport_back: {saved_docs.passport_back}")
            print(f"  license_front: {saved_docs.license_front}")
            print(f"  license_back: {saved_docs.license_back}")
            print(f"  driver_with_license: {saved_docs.driver_with_license}")
        else:
            print(f"❌ ОШИБКА: Документы НЕ найдены после сохранения!")
        
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

def extract_coordinates_from_plus_code(address: str):
    """Извлекает приблизительные координаты из Plus кодов для Газалкента"""
    if not address:
        return None, None
        
    # Ищем Plus код в адресе (формат: XXXX+XXX)
    plus_code_match = re.search(r'([A-Z0-9]{4}\+[A-Z0-9]{2,3})', address.upper())
    if not plus_code_match:
        return None, None
    
    plus_code = plus_code_match.group(1)
    logger.info(f"📍 Найден Plus код: {plus_code}")
    
    # ПРАВИЛЬНЫЕ координаты для основных Plus кодов
    plus_code_coords = {
        # Газалкент, Узбекистан (HQXX) - ИСПРАВЛЕННЫЕ КООРДИНАТЫ!
        'HQCQ+XCV': (41.6201, 69.9184),  # Газалкент близко к Ташкенту
        'HQCR+P7X': (41.6215, 69.9225),  # Газалкент близко к Ташкенту  
        'HQ9R+Q7H': (41.6195, 69.9155),  # Газалкент близко к Ташкенту
        'HQ9Q+P98': (41.6180, 69.9140),  # Газалкент близко к Ташкенту
        'HQCQ+': (41.62, 69.92),   # Базовые координаты для HQCQ+
        'HQCR+': (41.62, 69.92),   # Базовые координаты для HQCR+
        'HQ9R+': (41.62, 69.91),   # Базовые координаты для HQ9R+
        'HQ9Q+': (41.618, 69.914), # Базовые координаты для HQ9Q+
        'HQ9V+': (41.615, 69.925), # Базовые координаты для HQ9V+
        
        # Ош, Кыргызстан (GPXX)
        'GP2Q+VX': (40.515000, 72.800000),   # Ош центр
        'GP32+65': (40.505000, 72.801000),   # Ош район
        'GP2Q+': (40.515, 72.80),            # Базовые для GP2Q+
        'GP32+': (40.505, 72.801),           # Базовые для GP32+
        
        # Другие районы Кыргызстана (GRXX, HVXX)
        'GRMW+4G': (40.500000, 72.950000),   # Медресе район
        'HV2G+9XR': (40.520000, 72.980000),  # Кыргыз-Чек
        'GRMW+': (40.50, 72.95),             # Базовые для GRMW+
        'HV2G+': (40.52, 72.98),             # Базовые для HV2G+
    }
    
    # Точное совпадение
    if plus_code in plus_code_coords:
        lat, lng = plus_code_coords[plus_code]
        logger.info(f"📍 Точное совпадение Plus кода {plus_code}: {lat}, {lng}")
        return lat, lng
    
    # Приблизительное совпадение по первым 4 символам
    base_code = plus_code[:5]  # HQCQ+, HQCR+, etc.
    if base_code in plus_code_coords:
        lat, lng = plus_code_coords[base_code]
        # Добавляем небольшую случайность для уникальности
        lat += (random.random() - 0.5) * 0.001  # ±50 метров
        lng += (random.random() - 0.5) * 0.001
        logger.info(f"📍 Приблизительное совпадение Plus кода {plus_code} -> {base_code}: {lat}, {lng}")
        return lat, lng
    
    # Если не найдено точного совпадения, используем координаты в зависимости от префикса
    if plus_code.startswith('HQ'):
        # Газалкент, Узбекистан (близко к Ташкенту!)
        lat = 41.62 + (random.random() - 0.5) * 0.01
        lng = 69.92 + (random.random() - 0.5) * 0.01
        logger.info(f"📍 Использованы общие координаты Газалкента для {plus_code}: {lat}, {lng}")
    elif plus_code.startswith('GP'):
        # Ош, Кыргызстан
        lat = 40.51 + (random.random() - 0.5) * 0.01
        lng = 72.80 + (random.random() - 0.5) * 0.01
        logger.info(f"📍 Использованы общие координаты Оша для {plus_code}: {lat}, {lng}")
    elif plus_code.startswith('GR') or plus_code.startswith('HV'):
        # Другие районы Кыргызстана
        lat = 40.50 + (random.random() - 0.5) * 0.02
        lng = 72.90 + (random.random() - 0.5) * 0.10
        logger.info(f"📍 Использованы общие координаты Кыргызстана для {plus_code}: {lat}, {lng}")
    else:
        # По умолчанию - Газалкент (близко к Ташкенту!)
        lat = 41.62 + (random.random() - 0.5) * 0.01
        lng = 69.92 + (random.random() - 0.5) * 0.01
        logger.info(f"📍 Использованы координаты по умолчанию для {plus_code}: {lat}, {lng}")
    
    return lat, lng

@app.post("/api/admin/orders/")
async def create_order_from_form(
    request: Request,
    db: Session = Depends(get_db),
    order_number: str = Form(...),
    order_date: str = Form(...),
    order_time: str = Form(...),
    route_number: str = Form(...),
    driver_id: Optional[int] = Form(None),
    tariff: str = Form(...),
    payment_method: str = Form(...),
    origin: str = Form(...),
    destination: str = Form(...),
    origin_lat: Optional[str] = Form(""),
    origin_lng: Optional[str] = Form(""),
    destination_lat: Optional[str] = Form(""),
    destination_lng: Optional[str] = Form(""),
    notes: Optional[str] = Form(None),
    price: Optional[str] = Form(None)
):
    """Создание заказа из формы диспетчерской"""
    try:
        logger.info(f"📝 Создание заказа: {order_number}")
        logger.info(f"📊 Данные заказа: driver_id={driver_id}, tariff={tariff}, price={price}")
        logger.info(f"📊 Все данные: order_date={order_date}, order_time={order_time}, origin={origin}, destination={destination}")
        logger.info(f"📍 Полученные координаты: origin=({origin_lat},{origin_lng}), destination=({destination_lat},{destination_lng})")
        
        # Проверяем существование водителя если он выбран
        if driver_id and driver_id != '':
            try:
                driver_id_int = int(driver_id)
                driver = crud.get_driver(db, driver_id=driver_id_int)
                if not driver:
                    raise HTTPException(status_code=404, detail="Водитель не найден")
                order_status = "Назначен"
                final_driver_id = driver_id_int
            except (ValueError, TypeError):
                raise HTTPException(status_code=400, detail="Некорректный ID водителя")
        else:
            order_status = "Ожидает водителя"
            final_driver_id = None
        
        # Конвертируем цену
        order_price = None
        if price and price.strip():
            try:
                order_price = float(price.strip())
            except ValueError:
                logger.warning(f"⚠️ Некорректная цена: {price}")
        
        # Конвертируем координаты в числа (если указаны)
        final_origin_lat = None
        final_origin_lng = None
        final_destination_lat = None
        final_destination_lng = None
        
        try:
            if origin_lat and origin_lat.strip():
                final_origin_lat = float(origin_lat.strip())
            if origin_lng and origin_lng.strip():
                final_origin_lng = float(origin_lng.strip())
            if destination_lat and destination_lat.strip():
                final_destination_lat = float(destination_lat.strip())
            if destination_lng and destination_lng.strip():
                final_destination_lng = float(destination_lng.strip())
        except ValueError as e:
            logger.warning(f"⚠️ Ошибка преобразования координат: {e}")
            # Не прерываем выполнение, просто оставляем координаты как None
        
        # Если координаты не указаны, пытаемся извлечь их из Plus кодов в адресах
        if not final_origin_lat and not final_origin_lng:
            final_origin_lat, final_origin_lng = extract_coordinates_from_plus_code(origin)
            if final_origin_lat:
                logger.info(f"📍 Извлечены координаты отправления из Plus кода: {final_origin_lat}, {final_origin_lng}")
        
        if not final_destination_lat and not final_destination_lng:
            final_destination_lat, final_destination_lng = extract_coordinates_from_plus_code(destination)
            if final_destination_lat:
                logger.info(f"📍 Извлечены координаты назначения из Plus кода: {final_destination_lat}, {final_destination_lng}")
        
        logger.info(f"📍 Итоговые координаты: origin=({final_origin_lat},{final_origin_lng}), destination=({final_destination_lat},{final_destination_lng})")

        print(f"🔧 DEBUG: Создаём OrderCreate с координатами:")
        print(f"🔧 DEBUG: final_origin_lat={final_origin_lat}, final_origin_lng={final_origin_lng}")
        print(f"🔧 DEBUG: final_destination_lat={final_destination_lat}, final_destination_lng={final_destination_lng}")

        # Создаём объект заказа
        order_data = schemas.OrderCreate(
            order_number=order_number,
            time=order_time,
            origin=origin,
            destination=destination,
            origin_lat=final_origin_lat,
            origin_lng=final_origin_lng,
            destination_lat=final_destination_lat,
            destination_lng=final_destination_lng,
            driver_id=final_driver_id,
            status=order_status,
            price=order_price,
            tariff=tariff,
            notes=notes,
            payment_method=payment_method
        )
        
        # Создаём заказ в БД
        print(f"🔧 DEBUG: Вызываем crud.create_order...")
        try:
            new_order = crud.create_order(db=db, order=order_data)
            print(f"🔧 DEBUG: create_order выполнен успешно, new_order.id={new_order.id}")
            print(f"🔧 DEBUG: Сохранённые координаты: origin_lat={new_order.origin_lat}, origin_lng={new_order.origin_lng}")
            print(f"🔧 DEBUG: Сохранённые координаты: destination_lat={new_order.destination_lat}, destination_lng={new_order.destination_lng}")
            logger.info(f"✅ Заказ {order_number} создан успешно с ID: {new_order.id}")
            logger.info(f"📋 Статус заказа: {order_status}, Водитель: {final_driver_id or 'не назначен'}")
        except Exception as e:
            print(f"🔧 DEBUG: Ошибка в crud.create_order: {e}")
            print(f"🔧 DEBUG: Тип ошибки: {type(e)}")
            raise
        
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Заказ успешно создан",
                "order_id": new_order.id,
                "order_number": new_order.order_number
            }
        )
        
    except HTTPException:
        raise
    except ValidationError as e:
        logger.error(f"❌ Ошибка валидации данных заказа: {e}")
        error_details = []
        for error in e.errors():
            field = error['loc'][0] if error['loc'] else 'unknown'
            message = error['msg']
            error_details.append(f"{field}: {message}")
        raise HTTPException(
            status_code=422,
            detail=f"Ошибка валидации: {'; '.join(error_details)}"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка создания заказа: {e}")
        logger.error(f"🔍 Детали ошибки: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"🔍 Стек ошибки: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка создания заказа: {str(e)}"
        )

@app.get("/api/orders/map", response_class=JSONResponse)
async def get_orders_for_map(
    db: Session = Depends(get_db),
    status: Optional[str] = None,
    search: Optional[str] = None,
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Получение заказов для отображения на карте"""
    try:
        logger.info(f"🗺️ Запрос заказов для карты с фильтрами: status={status}, search={search}")
        
        # Получаем заказы с теми же фильтрами, что и в основном списке
        query = db.query(models.Order).join(models.Driver)
        
        # Применяем фильтры
        if status:
            query = query.filter(models.Order.status == status)
            
        if search:
            search_filter = or_(
                models.Order.order_number.ilike(f"%{search}%"),
                models.Order.origin.ilike(f"%{search}%"),
                models.Order.destination.ilike(f"%{search}%"),
                models.Driver.first_name.ilike(f"%{search}%"),
                models.Driver.last_name.ilike(f"%{search}%"),
                models.Driver.phone.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
            
        # Фильтры по дате
        if date and date != 'all':
            if date == 'today':
                today = datetime.now().date()
                query = query.filter(func.date(models.Order.created_at) == today)
            elif date == 'yesterday':
                yesterday = datetime.now().date() - timedelta(days=1)
                query = query.filter(func.date(models.Order.created_at) == yesterday)
            elif date == 'week':
                week_ago = datetime.now().date() - timedelta(days=7)
                query = query.filter(func.date(models.Order.created_at) >= week_ago)
        
        if start_date:
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(func.date(models.Order.created_at) >= start_date_obj)
            except ValueError:
                pass
                
        if end_date:
            try:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(func.date(models.Order.created_at) <= end_date_obj)
            except ValueError:
                pass
        
        # Получаем заказы
        orders = query.order_by(models.Order.created_at.desc()).limit(50).all()
        
        # Формируем данные для карты
        orders_data = []
        for order in orders:
            orders_data.append({
                "id": order.id,
                "order_number": order.order_number or str(order.id),
                "origin": order.origin,
                "destination": order.destination,
                "status": order.status or "Выполняется",
                "driver_name": f"{order.driver.first_name} {order.driver.last_name}",
                "driver_phone": order.driver.phone or "",
                "price": str(order.price) if order.price else "",
                "tariff": order.tariff or order.driver.tariff or "",
                "time": order.time,
                "created_at": order.created_at.strftime('%d.%m.%y %H:%M')
            })
        
        logger.info(f"✅ Найдено {len(orders_data)} заказов для карты")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "orders": orders_data,
                "total": len(orders_data)
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения заказов для карты: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "orders": []
            }
        )

@app.post("/api/orders/{order_id}/cancel", response_class=JSONResponse)
async def cancel_order(
    order_id: int,
    request: Request,
    db: Session = Depends(get_db),
    reason: Optional[str] = None
):
    """Отмена заказа диспетчером"""
    try:
        logger.info(f"🚫 Отмена заказа ID: {order_id}")
        
        # Получаем заказ из БД
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "Заказ не найден"
                }
            )
        
        # Проверяем, можно ли отменить заказ
        if order.status == "Отменен":
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Заказ уже отменен"
                }
            )
        
        # Обновляем статус заказа
        order.status = "Отменен"
        
        # Если указана причина, добавляем её в примечания
        if reason:
            current_notes = order.notes or ""
            order.notes = f"{current_notes}\n[ОТМЕНЕН] {reason}".strip()
        
        # Сохраняем изменения
        db.commit()
        db.refresh(order)
        
        logger.info(f"✅ Заказ #{order.order_number} (ID: {order_id}) успешно отменен")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Заказ #{order.order_number} отменен",
                "order_id": order.id,
                "new_status": order.status
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка отмены заказа {order_id}: {e}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Ошибка отмены заказа: {str(e)}"
            }
        )

@app.post("/api/driver/{driver_id}/decline-order/{order_id}", response_class=JSONResponse)
async def decline_order_by_driver(
    driver_id: int,
    order_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Отклонение заказа водителем"""
    try:
        logger.info(f"🚫 Водитель {driver_id} отклоняет заказ {order_id}")
        
        # Получаем заказ из БД
        order = db.query(models.Order).filter(
            models.Order.id == order_id,
            models.Order.driver_id == driver_id
        ).first()
        
        if not order:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "Заказ не найден или не назначен этому водителю"
                }
            )
        
        # Проверяем, можно ли отклонить заказ
        if order.status in ["Завершен", "Отменен"]:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Нельзя отклонить заказ со статусом '{order.status}'"
                }
            )
        
        # Обновляем статус заказа
        order.status = "Отклонен водителем"
        
        # Добавляем причину в примечания
        current_notes = order.notes or ""
        order.notes = f"{current_notes}\n[ОТКЛОНЕН ВОДИТЕЛЕМ] {datetime.now().strftime('%d.%m.%Y %H:%M')}".strip()
        
        # Уменьшаем активность водителя на 10 баллов
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if driver:
            current_activity = getattr(driver, 'activity', 50) or 50
            new_activity = max(0, current_activity - 10)
            driver.activity = new_activity
            logger.info(f"📉 Активность водителя {driver_id}: {current_activity} -> {new_activity}")
        
        # Сохраняем изменения
        db.commit()
        db.refresh(order)
        
        logger.info(f"✅ Заказ #{order.order_number} отклонен водителем {driver_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Заказ #{order.order_number} отклонен",
                "order_id": order.id,
                "new_status": order.status,
                "new_activity": getattr(driver, 'activity', 0) if driver else 0
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка отклонения заказа {order_id} водителем {driver_id}: {e}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Ошибка отклонения заказа: {str(e)}"
            }
        )

@app.post("/api/driver/{driver_id}/accept-order/{order_id}", response_class=JSONResponse)
async def accept_order_by_driver(
    driver_id: int,
    order_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Принятие заказа водителем"""
    try:
        logger.info(f"✅ Водитель {driver_id} принимает заказ {order_id}")
        
        # Получаем заказ из БД
        order = db.query(models.Order).filter(
            models.Order.id == order_id,
            models.Order.driver_id == driver_id
        ).first()
        
        if not order:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "Заказ не найден или не назначен этому водителю"
                }
            )
        
        # Проверяем, можно ли принять заказ
        if order.status in ["Завершен", "Отменен", "Отклонен водителем"]:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Нельзя принять заказ со статусом '{order.status}'"
                }
            )
        
        # Обновляем статус заказа
        order.status = "Выполняется"
        
        # Добавляем информацию в примечания
        current_notes = order.notes or ""
        order.notes = f"{current_notes}\n[ПРИНЯТ ВОДИТЕЛЕМ] {datetime.now().strftime('%d.%m.%Y %H:%M')}".strip()
        
        # Увеличиваем активность водителя на 4 балла
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if driver:
            current_activity = getattr(driver, 'activity', 50) or 50
            new_activity = min(100, current_activity + 4)
            driver.activity = new_activity
            logger.info(f"📈 Активность водителя {driver_id}: {current_activity} -> {new_activity}")
        
        # Сохраняем изменения
        db.commit()
        db.refresh(order)
        
        logger.info(f"✅ Заказ #{order.order_number} принят водителем {driver_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Заказ #{order.order_number} принят",
                "order_id": order.id,
                "new_status": order.status,
                "new_activity": getattr(driver, 'activity', 0) if driver else 0
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка принятия заказа {order_id} водителем {driver_id}: {e}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Ошибка принятия заказа: {str(e)}"
            }
        )

@app.get("/api/driver/{driver_id}/new-orders", response_class=JSONResponse)
async def get_new_orders_for_driver(driver_id: int, db: Session = Depends(get_db)):
    """Получение новых заказов для водителя"""
    try:
        # Получаем заказы назначенные этому водителю
        new_orders = db.query(models.Order).filter(
            models.Order.driver_id == driver_id,
            models.Order.status.in_(["Ожидает водителя", "Назначен"])
        ).order_by(models.Order.created_at.desc()).limit(1).all()
        
        # Альтернативный поиск заказов без назначенного водителя
        if not new_orders:
            new_orders = db.query(models.Order).filter(
                models.Order.status == "Ожидает водителя",
                models.Order.driver_id.is_(None)
            ).order_by(models.Order.created_at.desc()).limit(1).all()
        
        logger.info(f"📋 Найдено заказов для водителя {driver_id}: {len(new_orders)}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "orders": [
                    {
                        "id": order.id,
                        "order_number": order.order_number,
                        "origin": order.origin,
                        "destination": order.destination,
                        "status": order.status,
                        "price": order.price,
                        "tariff": order.tariff,
                        "notes": order.notes,
                        "time": order.time,
                        "created_at": order.created_at.isoformat() if order.created_at else None,
                        "origin_lat": order.origin_lat,
                        "origin_lng": order.origin_lng,
                        "destination_lat": order.destination_lat,
                        "destination_lng": order.destination_lng
                    }
                    for order in new_orders
                ]
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения заказов для водителя {driver_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e),
                "orders": []
            }
        )



@app.post("/api/driver/{driver_id}/start-trip/{order_id}", response_class=JSONResponse)
async def start_trip(driver_id: int, order_id: int, db: Session = Depends(get_db)):
    """Водитель начинает поездку"""
    try:
        order = db.query(models.Order).filter(
            models.Order.id == order_id,
            models.Order.driver_id == driver_id
        ).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Заказ не найден")
        
        if order.status != "Принят":
            raise HTTPException(status_code=400, detail="Заказ не может быть начат")
        
        order.status = "Выполняется"
        db.commit()
        
        logger.info(f"✅ Водитель {driver_id} начал поездку по заказу {order_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Поездка начата",
                "order_status": order.status
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка начала поездки {order_id}: {e}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/api/driver/{driver_id}/active-trip", response_class=JSONResponse)
async def get_active_trip(driver_id: int, db: Session = Depends(get_db)):
    """Получение активной поездки водителя для восстановления состояния"""
    try:
        # Ищем активный заказ водителя
        active_order = db.query(models.Order).filter(
            models.Order.driver_id == driver_id,
            models.Order.status.in_(["Принят", "Выполняется"])
        ).first()
        
        if not active_order:
            return JSONResponse(
                status_code=200,
                content={"success": True, "trip": None}
            )
        
        logger.info(f"🔄 Найдена активная поездка для водителя {driver_id}: заказ #{active_order.order_number}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "trip": {
                    "id": active_order.id,
                    "order_number": active_order.order_number,
                    "status": active_order.status,
                    "price": active_order.price,
                    "origin": active_order.origin,
                    "destination": active_order.destination,
                    "pickup_lat": active_order.origin_lat,
                    "pickup_lng": active_order.origin_lng,
                    "destination_lat": active_order.destination_lat,
                    "destination_lng": active_order.destination_lng
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения активной поездки {driver_id}: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.post("/api/driver/{driver_id}/complete-trip/{order_id}", response_class=JSONResponse)
async def complete_trip(
    driver_id: int, 
    order_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    """Завершение поездки с расчетом оплаты по проценту выполнения"""
    try:
        body = await request.json()
        completion_percentage = body.get('completion_percentage', 100)
        rating = body.get('rating', 5)
        
        # Получаем заказ
        order = db.query(models.Order).filter(
            models.Order.id == order_id,
            models.Order.driver_id == driver_id
        ).first()
        
        if not order:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": "Заказ не найден или не назначен этому водителю"
                }
            )
        
        if order.status not in ["Выполняется", "Принят"]:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Нельзя завершить заказ со статусом '{order.status}'"
                }
            )
        
        # Рассчитываем итоговую стоимость
        original_price = order.price or 433
        final_price = round(original_price * (completion_percentage / 100))
        
        # Обновляем заказ
        order.status = "Завершен"
        order.price = final_price
        order.notes = (order.notes or "") + f"\n[ЗАВЕРШЕН] {completion_percentage}% маршрута. Оценка: {rating}⭐"
        
        # Обновляем активность водителя
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        activity_gain = 0
        new_activity = 50
        new_balance = 0
        
        if driver:
            activity_gain = round(completion_percentage / 25)  # 1 балл за каждые 25%
            current_activity = getattr(driver, 'activity', 50) or 50
            new_activity = min(100, current_activity + activity_gain)
            driver.activity = new_activity
            
            # Обновляем баланс водителя
            current_balance = getattr(driver, 'balance', 0) or 0
            new_balance = current_balance + final_price
            driver.balance = new_balance
            
            logger.info(f"💰 Водитель {driver_id}: +{final_price} СОМ, активность {current_activity} -> {new_activity}")
        
        # Сохраняем изменения
        db.commit()
        db.refresh(order)
        
        logger.info(f"🏁 Поездка завершена: заказ #{order.order_number}, {completion_percentage}%, {final_price} СОМ")
        logger.info(f"💰 Водитель {driver_id}: активность {new_activity}, баланс {new_balance}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Поездка завершена ({completion_percentage}%)",
                "order_id": order.id,
                "completion_percentage": completion_percentage,
                "original_price": original_price,
                "final_price": final_price,
                "activity_gain": activity_gain if driver else 0,
                "new_activity": new_activity if driver else 0,
                "new_balance": new_balance if driver else 0
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка завершения поездки {order_id}: {e}")
        import traceback
        logger.error(f"❌ Полная ошибка: {traceback.format_exc()}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Ошибка завершения поездки: {str(e)}"
            }
        )

@app.get("/api/available-tariffs", response_class=JSONResponse)
async def get_available_tariffs(db: Session = Depends(get_db)):
    """Получение доступных тарифов на основе активных водителей"""
    try:
        # Получаем активных водителей
        active_drivers = db.query(models.Driver).filter(
            models.Driver.status == "accepted"
        ).all()
        
        # Подсчитываем количество водителей по тарифам
        tariff_counts = {}
        tariff_availability = {}
        
        for driver in active_drivers:
            tariff = driver.tariff
            if tariff:  # Проверяем что тариф не None
                tariff_counts[tariff] = tariff_counts.get(tariff, 0) + 1
        
        # Маппинг тарифов (из БД в frontend)
        tariff_mapping = {
            'Бюджетный': 'economy',
            'Эконом': 'economy', 
            'Стандартный': 'comfort',
            'Комфорт': 'comfort',
            'Комфорт+': 'comfort-plus',
            'Бизнес': 'business',
            'Люкс': 'business'
        }
        
        # Все возможные frontend тарифы
        all_frontend_tariffs = ['economy', 'comfort', 'comfort-plus', 'business']
        
        # Инициализируем все frontend тарифы как недоступные
        for frontend_tariff in all_frontend_tariffs:
            tariff_availability[frontend_tariff] = {
                'available': False,
                'drivers_count': 0,
                'estimated_time': 20  # Время ожидания если нет водителей
            }
        
        # Обновляем доступность на основе реальных данных
        for db_tariff, frontend_tariff in tariff_mapping.items():
            count = tariff_counts.get(db_tariff, 0)
            if count > 0:
                # Если тариф уже был инициализирован, добавляем водителей
                if frontend_tariff in tariff_availability:
                    tariff_availability[frontend_tariff]['drivers_count'] += count
                    tariff_availability[frontend_tariff]['available'] = True
                    tariff_availability[frontend_tariff]['estimated_time'] = min(5 + count, 10)  # Меньше времени при большем количестве водителей
                else:
                    tariff_availability[frontend_tariff] = {
                        'available': True,
                        'drivers_count': count,
                        'estimated_time': 5 + min(count, 5)
                    }
        
        logger.info(f"📊 Доступные тарифы: {tariff_availability}")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "tariffs": tariff_availability,
                "total_drivers": len(active_drivers)
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения доступных тарифов: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Ошибка получения тарифов: {str(e)}"
            }
        )

@app.post("/api/user-orders/", response_class=JSONResponse)
async def create_user_order(request: Request, db: Session = Depends(get_db)):
    """Создание заказа от пользователя мобильного приложения"""
    try:
        # Логирование входящего запроса
        logger.info("📱 Получен запрос на создание заказа от пользователя")
        
        # Получаем данные из запроса
        try:
            data = await request.json()
            logger.info(f"📋 Данные запроса: {data}")
        except Exception as json_error:
            logger.error(f"❌ Ошибка парсинга JSON: {json_error}")
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Некорректный JSON в запросе"}
            )
        
        # Валидация данных
        required_fields = ['origin', 'destination', 'tariff', 'payment_method']
        for field in required_fields:
            if not data.get(field):
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": f"Поле {field} обязательно"}
                )
        
        # Генерируем номер заказа
        import datetime
        import random
        order_number = f"WZ{datetime.datetime.now().strftime('%Y%m%d')}{random.randint(1000, 9999)}"
        
        # РЕАЛЬНАЯ ЛОГИКА: создаём заказ БЕЗ назначения водителя
        # Заказ будет ожидать принятия водителем
        order_data = schemas.OrderCreate(
            order_number=order_number,
            time=datetime.datetime.now().strftime("%H:%M"),
            origin=data['origin'],
            destination=data['destination'],
            driver_id=None,  # НЕТ водителя - заказ ждёт принятия
            status="Ожидает принятия",  # Статус ожидания
            price=data.get('price', 0),
            tariff=data['tariff'],
            notes=data.get('comment', ''),
            payment_method=data['payment_method']
        )
        
        new_order = crud.create_order(db=db, order=order_data)
        
        logger.info(f"📱 Заказ {order_number} создан пользователем, ожидает принятия водителем")
        
        # Возвращаем заказ БЕЗ данных водителя - он пока не назначен
        return JSONResponse(
            status_code=201,
            content={
                "success": True,
                "message": "Заказ создан и ожидает принятия водителем",
                "order_id": new_order.id,
                "order_number": new_order.order_number,
                "status": "waiting_for_driver",  # Статус для фронта
                "tariff": data['tariff']
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания заказа пользователем: {str(e)}")
        import traceback
        logger.error(f"❌ Полная ошибка: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Ошибка создания заказа: {str(e)}"
            }
        )

@app.post("/api/orders/{order_id}/cancel", response_class=JSONResponse)
async def cancel_order(order_id: int, request: CancelOrderRequest, db: Session = Depends(get_db)):
    """Отмена заказа клиентом или водителем"""
    try:
        # Находим заказ
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Заказ не найден"}
            )
        
        # Проверяем статус заказа
        if order.status not in ["Ожидает водителя", "Выполняется", "Принят"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Заказ нельзя отменить"}
            )
        
        # Определяем статус в зависимости от того, кто отменяет
        if request.cancelled_by == "client":
            order.status = "Отменен заказчиком"
            logger.info(f"❌ Заказ {order.order_number} отменен заказчиком")
        elif request.cancelled_by == "driver":
            order.status = "Отклонен водителем"
            logger.info(f"❌ Заказ {order.order_number} отклонен водителем")
        else:
            order.status = "Отменен"
            logger.info(f"❌ Заказ {order.order_number} отменен")
        
        # Сохраняем причину отмены если она указана
        if request.reason:
            # В реальной системе нужно добавить поле cancel_reason в модель Order
            logger.info(f"📝 Причина отмены: {request.reason}")
        
        db.commit()
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "Заказ успешно отменен",
                "cancelled_by": request.cancelled_by,
                "new_status": order.status
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Ошибка отмены заказа: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Ошибка отмены заказа: {str(e)}"
            }
        )

@app.get("/api/orders/{order_id}/status", response_class=JSONResponse)
async def get_order_status(order_id: int, db: Session = Depends(get_db)):
    """Получение статуса заказа"""
    try:
        # Находим заказ
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Заказ не найден"}
            )
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "order": {
                    "id": order.id,
                    "order_number": order.order_number,
                    "status": order.status,
                    "origin": order.origin,
                    "destination": order.destination,
                    "driver_id": order.driver_id,
                    "price": order.price,
                    "created_at": order.created_at.isoformat() if order.created_at else None
                }
            }
        )
        
    except Exception as e:
        print(f"❌ Ошибка получения статуса заказа: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Ошибка сервера: {str(e)}"}
        )

@app.get("/api/orders/test", response_class=JSONResponse)
async def test_orders_api():
    """Тестовый endpoint для проверки API orders"""
    return JSONResponse(
        status_code=200,
        content={"success": True, "message": "API orders работает!"}
    )

@app.post("/api/orders/complete-with-progress")
async def complete_order_with_progress(request: Request, db: Session = Depends(get_db)):
    """Завершение поездки с прогрессом"""
    print("🎯 ENDPOINT ВЫЗВАН! /api/orders/complete-with-progress")
    try:
        data = await request.json()
        order_id = data.get("order_id")
        driver_id = data.get("driver_id")
        completion_type = data.get("completion_type", "full")  # full or partial
        final_latitude = data.get("final_latitude")
        final_longitude = data.get("final_longitude")
        
        print(f"🏁 Завершение поездки: order_id={order_id}, driver_id={driver_id}, type={completion_type}")
        print(f"📍 Координаты: lat={final_latitude}, lng={final_longitude}")
        print(f"📋 Тип данных: order_id={type(order_id)}, driver_id={type(driver_id)}")
        
        # Проверяем обязательные параметры
        if not all([order_id, driver_id]):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Не указаны order_id или driver_id"}
            )
        
        # Находим заказ
        print(f"🔍 Ищем заказ: order_id={order_id}, driver_id={driver_id}")
        order = db.query(models.Order).filter(
            models.Order.id == order_id,
            models.Order.driver_id == driver_id
        ).first()
        
        if not order:
            print(f"❌ Заказ не найден: order_id={order_id}, driver_id={driver_id}")
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Заказ не найден или не принадлежит водителю"}
            )
        
        print(f"✅ Заказ найден: #{order.order_number}, статус={order.status}, цена={order.price}")
        
        # Проверяем статус заказа
        if order.status in ["Завершен", "Отменен"]:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"Заказ уже {order.status.lower()}"}
            )
        
        # Получаем водителя
        print(f"🔍 Ищем водителя: driver_id={driver_id}")
        driver = db.query(models.Driver).filter(models.Driver.id == driver_id).first()
        if not driver:
            print(f"❌ Водитель не найден: driver_id={driver_id}")
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Водитель не найден"}
            )
        
        print(f"✅ Водитель найден: {driver.full_name}, баланс={driver.balance}")
        
        # Рассчитываем прогресс и оплату
        if completion_type == "partial":
            # Досрочное завершение - базовая оплата независимо от прогресса
            progress_percentage = 0.0  # Досрочное завершение
            actual_payment = order.price or 0.0  # Полная оплата даже при досрочном завершении
        else:
            # Полное завершение
            progress_percentage = 100.0
            actual_payment = order.price or 0.0
        
        # Обновляем заказ
        order.status = "Завершен"
        order.progress_percentage = progress_percentage
        order.actual_price = actual_payment
        order.completed_at = datetime.now()
        
        # Обновляем баланс водителя
        driver.balance = (driver.balance or 0.0) + actual_payment
        
        # Создаем транзакцию
        order_number = getattr(order, 'order_number', str(order.id)) if order else str(order_id)
        print(f"💳 Создаем транзакцию: водитель={driver_id}, сумма={actual_payment}, заказ={order_number}")
        
        transaction = models.BalanceTransaction(
            driver_id=int(driver_id),
            amount=float(actual_payment),
            type="deposit",
            status="completed",
            description=f"Оплата за заказ #{order_number}"
        )
        db.add(transaction)
        print(f"✅ Транзакция добавлена в сессию")
        
        # Увеличиваем активность водителя
        current_activity = getattr(driver, 'activity', 50) or 50
        new_activity = min(100, current_activity + 2)  # +2 балла за завершение
        driver.activity = new_activity
        
        # Сохраняем изменения
        print(f"💾 Сохраняем изменения в БД...")
        try:
            db.commit()
            print(f"✅ Commit успешен")
            db.refresh(order)
            db.refresh(driver)
            print(f"✅ Refresh объектов успешен")
        except Exception as commit_error:
            print(f"❌ Ошибка при commit: {str(commit_error)}")
            db.rollback()
            raise commit_error
        
        print(f"✅ Заказ #{order.order_number} завершен. Оплата: {actual_payment} сом")
        print(f"💰 Баланс водителя обновлен: {driver.balance} сом")
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": f"Заказ #{order.order_number} успешно завершен",
                "order_id": order.id,
                "progress_percentage": progress_percentage,
                "actual_payment": actual_payment,
                "driver_balance": driver.balance,
                "completion_type": completion_type,
                "completed_at": order.completed_at.isoformat() if order.completed_at else None
            }
        )
        
    except Exception as e:
        print(f"❌ Ошибка завершения поездки: {str(e)}")
        import traceback
        print(f"❌ Полная ошибка: {traceback.format_exc()}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Ошибка завершения поездки: {str(e)}"
            }
        )

# API для обновления позиции водителя
@app.post("/api/driver/update-location", response_class=JSONResponse)
async def update_driver_location(request: UpdateDriverLocationRequest, db: Session = Depends(get_db)):
    """Обновление позиции водителя и расчет прогресса заказа"""
    try:
        # Находим водителя
        driver = db.query(models.Driver).filter(models.Driver.id == request.driver_id).first()
        if not driver:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Водитель не найден"}
            )
        
        # Обновляем позицию водителя
        driver.current_lat = request.latitude
        driver.current_lng = request.longitude
        driver.last_location_update = datetime.now()
        driver.is_online = True
        
        response_data = {
            "success": True,
            "driver_id": driver.id,
            "location_updated": True
        }
        
        # Если указан заказ, рассчитываем прогресс
        if request.order_id:
            order = db.query(models.Order).filter(
                models.Order.id == request.order_id,
                models.Order.driver_id == request.driver_id
            ).first()
            
            if order and order.status in ["Выполняется", "В пути"]:
                # Рассчитываем прогресс
                progress_data = calculate_order_progress(order, request.latitude, request.longitude)
                
                # Обновляем данные заказа
                order.completed_distance = progress_data["completed_distance"]
                order.progress_percentage = progress_data["progress"]
                
                # Рассчитываем фактическую оплату
                if order.price:
                    actual_payment = calculate_actual_payment(order.price, progress_data["progress"])
                    order.actual_price = actual_payment
                
                response_data.update({
                    "order_progress": {
                        "progress_percentage": progress_data["progress"],
                        "completed_distance": progress_data["completed_distance"],
                        "remaining_distance": progress_data["remaining_distance"],
                        "total_distance": progress_data["total_distance"],
                        "actual_payment": order.actual_price
                    }
                })
        
        db.commit()
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"❌ Ошибка обновления позиции водителя: {str(e)}")
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Ошибка сервера: {str(e)}"}
        )

# Endpoint перенесен в app/routers/orders.py

# API для получения прогресса заказа
@app.get("/api/order/{order_id}/progress", response_class=JSONResponse)
async def get_order_progress(order_id: int, db: Session = Depends(get_db)):
    """Получение текущего прогресса выполнения заказа"""
    try:
        order = db.query(models.Order).filter(models.Order.id == order_id).first()
        if not order:
            return JSONResponse(
                status_code=404,
                content={"success": False, "error": "Заказ не найден"}
            )
        
        # Если есть водитель, получаем его текущую позицию
        current_progress = 0.0
        if order.driver and order.driver.current_lat and order.driver.current_lng:
            progress_data = calculate_order_progress(
                order, 
                order.driver.current_lat, 
                order.driver.current_lng
            )
            current_progress = progress_data["progress"]
        
        return JSONResponse(content={
            "success": True,
            "order_id": order.id,
            "status": order.status,
            "progress_percentage": order.progress_percentage or current_progress,
            "completed_distance": order.completed_distance or 0.0,
            "total_distance": order.total_distance or 0.0,
            "base_price": order.price,
            "actual_price": order.actual_price,
            "driver_location": {
                "lat": order.driver.current_lat if order.driver else None,
                "lng": order.driver.current_lng if order.driver else None,
                "last_update": order.driver.last_location_update.isoformat() if order.driver and order.driver.last_location_update else None
            } if order.driver else None
        })
        
    except Exception as e:
        logger.error(f"❌ Ошибка получения прогресса заказа: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Ошибка сервера: {str(e)}"}
        )

if __name__ == "__main__":
    import uvicorn
    
    # Отладочная информация перед запуском
    print("🚀 Запускаем uvicorn сервер...")
    print(f"📁 Все зарегистрированные роуты:")
    for route in app.routes:
        if hasattr(route, 'path'):
            print(f"  - {route.methods} {route.path}")
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True) 