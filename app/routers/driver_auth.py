from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from .. import crud, models, schemas
from ..database import get_db
from ..models import TokenResponse

router = APIRouter(
    prefix="/driver",
    tags=["driver-auth"],
    responses={404: {"description": "Driver not found"}},
)

# Модель запроса для входа водителя
class DriverLoginRequest(BaseModel):
    phone: str

# Модель запроса для подтверждения кода
class VerifyCodeRequest(BaseModel):
    phone: str
    code: str

@router.post("/login", response_model=dict)
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

@router.post("/verify-code", response_model=TokenResponse)
async def verify_code(request: VerifyCodeRequest, response: Response = None, db: Session = Depends(get_db)):
    """
    ТЕСТОВЫЙ РЕЖИМ: Любой номер телефона перенаправляется на +996111111111
    
    Возвращает JWT токен для фиксированного профиля.
    """
    # ТЕСТОВЫЙ РЕЖИМ: Всегда используем фиксированный профиль
    FIXED_PHONE = "996111111111"  # Без пробелов и дефисов
    
    raw_phone = request.phone
    input_phone = ''.join(filter(str.isdigit, request.phone))
    
    print(f"🔄 ТЕСТОВЫЙ РЕЖИМ: Введен номер {raw_phone} ({input_phone})")
    print(f"🎯 Перенаправляем на фиксированный профиль: {FIXED_PHONE}")
    
    # Проверяем код (всегда 1111 в тестовом режиме)
    if request.code != "1111":
        print(f"❌ Неверный код: {request.code}, ожидается 1111")
        raise HTTPException(status_code=400, detail="Неверный код подтверждения")
    
    print(f"✅ Код верный: {request.code}")
    
    # Ищем пользователя с фиксированным номером
    user = crud.get_driver_user_by_phone(db, FIXED_PHONE)
    
    if not user:
        print(f"🆕 Создаем нового пользователя с номером {FIXED_PHONE}")
        try:
            user = crud.create_driver_user(db, schemas.DriverUserCreate(
                phone=FIXED_PHONE,
                first_name="Тестовый",
                last_name="Водитель"
            ))
            print(f"✅ Пользователь создан: id={user.id}")
        except Exception as e:
            print(f"❌ Ошибка создания пользователя: {e}")
            raise HTTPException(status_code=500, detail="Ошибка создания пользователя")
    else:
        print(f"✅ Найден существующий пользователь: id={user.id}")
    
    print(f"👤 Пользователь: id={user.id}, имя={user.first_name}, driver_id={user.driver_id}")
    
    # Отмечаем пользователя как верифицированного
    user_update = schemas.DriverUserUpdate(is_verified=True)
    user = crud.update_driver_user(db, user.id, user_update)
    
    # Обновляем время последнего входа
    try:
        crud.update_last_login(db, user.id)
    except Exception as e:
        print(f"⚠️ Ошибка обновления времени входа: {e}")
    
    # Проверяем, связан ли пользователь с водителем
    has_driver = user.driver_id is not None
    driver_id = user.driver_id
    print(f"🔍 Проверка водителя: driver_id={driver_id}, has_driver={has_driver}")
    
    # Если нет связанного водителя, ищем по фиксированному номеру
    if not has_driver:
        print(f"🔍 Ищем водителя с номером {FIXED_PHONE}")
        
        # Возможные форматы фиксированного номера в БД
        phone_formats = [
            FIXED_PHONE,                    # 996111111111
            "+996111111111",                # +996111111111  
            "996 111-111-111",              # С пробелами и дефисами
            "+996 111-111-111",             # С + и форматированием
            "0111111111"                    # Может быть сохранен в локальном формате
        ]
        
        for phone_format in phone_formats:
            print(f"🔍 Поиск водителя с форматом: {phone_format}")
            driver = db.query(models.Driver).filter(models.Driver.phone == phone_format).first()
            
            if driver:
                print(f"✅ Найден водитель: id={driver.id}, имя={driver.full_name}")
                # Связываем пользователя с найденным водителем
                user.driver_id = driver.id
                db.commit()
                
                has_driver = True
                driver_id = driver.id
                print(f"🔗 Связали пользователя с водителем: user_id={user.id}, driver_id={driver_id}")
                break
        
        if not has_driver:
            print(f"⚠️ Водитель с номером {FIXED_PHONE} не найден в БД")
    
    print(f"Итоговый результат: has_driver={has_driver}, driver_id={driver_id}")
    
    # Создаем JWT токен
    import jose.jwt
    import secrets
    from datetime import datetime, timedelta
    
    # Секретный ключ для подписи токена (в продакшене должен быть в переменных окружения)
    SECRET_KEY = "wazir_secret_key_2024"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30 * 24 * 60  # 30 дней
    
    # Создаем payload для токена
    to_encode = {
        "sub": str(user.id),
        "user_id": user.id,
        "phone": user.phone,
        "has_driver": has_driver,
        "driver_id": driver_id,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    }
    
    # Генерируем токен
    access_token = jose.jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    print(f"Сгенерирован токен для пользователя {user.id}: {access_token[:50]}...")
    
    # Возвращаем токен и информацию о пользователе
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        has_driver=has_driver,
        driver_id=driver_id
    )
