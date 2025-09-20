# Настройка 2ГИС API

## Проблема
В логах видна ошибка 403 (Forbidden) при обращении к 2ГИС Routing API:
```
POST https://routing.api.2gis.com/routing/7.0.0/global?key=... 403 (Forbidden)
```

## Что нужно сделать

### 1. Получить API ключ

1. Зарегистрируйтесь на [2ГИС Platform](https://platform.2gis.ru/)
2. Войдите в личный кабинет
3. Создайте новый проект
4. Получите API ключ для:
   - **Routing API** (для построения маршрутов)
   - **MapGL JS API** (для отображения карты)

### 2. Настроить переменные окружения

Создайте файл `.env` в корне проекта:

```env
# Database Configuration
DATABASE_URL=postgresql://wazir_user:wazir_password@localhost:5432/wazir_db

# JWT Configuration
SECRET_KEY=your_secret_key_here_change_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Redis Configuration (optional)
REDIS_URL=redis://localhost:6379

# Application Settings
DEBUG=False
LOG_LEVEL=INFO
HOST=0.0.0.0
PORT=8000

# File Upload Settings
MAX_FILE_SIZE=10485760
UPLOAD_DIR=uploads

# 2GIS API Configuration
# Получите ключи на https://platform.2gis.ru/
TWOGIS_API_KEY=YOUR_ROUTING_API_KEY_HERE
TWOGIS_SECRET_KEY=

# Google Maps API Configuration  
GOOGLE_MAPS_API=AIzaSyCgctqtqKOus6A6cDJaOBqsyo4-3r3zuQA
```

### 3. Обновить API ключ в HTML файле

В файле `app/templates/driver/online.html` замените строку:

```javascript
key: 'your_mapgl_api_key_here', // API ключ для MapGL - замените на рабочий ключ
```

На:

```javascript
key: 'ВАШ_MAPGL_API_КЛЮЧ_ЗДЕСЬ', // API ключ для MapGL
```

### 4. Проверить работу

1. Перезапустите приложение
2. Откройте страницу водителя
3. Попробуйте построить маршрут
4. В логах должно появиться: `🔑 API ключ 2GIS настроен: Да`

## Что исправлено

✅ Обновлен URL API с версии 2.0 на 7.0.0
✅ Изменен формат запроса с GET на POST с JSON телом
✅ Добавлена поддержка новых параметров API
✅ Исправлена обработка ответа API
✅ Убран захардкоженный API ключ из кода
✅ Добавлен fallback на прямую линию при ошибках

## Документация

- [2ГИС Routing API 7.0.0](https://docs.2gis.com/ru/api/navigation/routing/overview)
- [Примеры использования](https://docs.2gis.com/ru/api/navigation/routing/examples)
- [Platform Manager](https://platform.2gis.ru/playground/routing)

## Поддерживаемые типы транспорта

- `driving` - автомобиль (по умолчанию)
- `walking` - пешеход
- `taxi` - такси
- `bicycle` - велосипед
- `scooter` - самокат
- `emergency` - экстренные службы
- `truck` - грузовой транспорт
- `motorcycle` - мотоцикл
