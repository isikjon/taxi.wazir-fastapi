# WAZIR MTT

API для управления водителями и заказами такси WAZIR.

## Особенности

- API на FastAPI с полной документацией
- Работа с базой данных PostgreSQL
- Система управления водителями, автомобилями и заказами
- Загрузка и хранение фотографий автомобилей
- Миграции базы данных с Alembic

## Структура проекта

```
fast/
├── alembic/              # Файлы для миграций БД
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── app/
│   ├── routers/          # Маршруты API
│   │   ├── drivers.py    # API для водителей
│   │   ├── cars.py       # API для автомобилей
│   │   └── orders.py     # API для заказов
│   ├── __init__.py
│   ├── crud.py           # CRUD операции
│   ├── database.py       # Настройки базы данных
│   ├── main.py           # Основной файл приложения
│   ├── models.py         # SQLAlchemy модели
│   └── schemas.py        # Pydantic схемы
├── uploads/              # Директория для загрузки файлов
│   └── cars/             # Фотографии автомобилей
├── .env                  # Переменные окружения
├── Dockerfile            # Для сборки Docker-образа
├── alembic.ini           # Конфигурация Alembic
└── requirements.txt      # Зависимости проекта
```

## Настройка и запуск

### Предварительные требования

- Python 3.8+
- PostgreSQL
- Docker (опционально)

### Установка и запуск локально

1. Клонировать репозиторий
2. Создать и активировать виртуальное окружение Python

```bash
python -m venv venv
source venv/bin/activate  # Для Linux/Mac
venv\Scripts\activate     # Для Windows
```

3. Установить зависимости

```bash
pip install -r requirements.txt
```

4. Создать файл .env с переменными окружения

```
DATABASE_URL=postgresql://cloud_user:SZaB%1noa!&0@kakdinugun.beget.app:5432/default_db
SECRET_KEY=wazir_secret_key_change_in_production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

5. Запустить миграции базы данных

```bash
alembic upgrade head
```

6. Запустить приложение

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Запуск с Docker

1. Собрать Docker-образ

```bash
docker build -t wazir-mtt .
```

2. Запустить контейнер

```bash
docker run -d -p 8000:8000 --name wazir-mtt wazir-mtt
```

## API

После запуска API будет доступно по адресу http://localhost:8000

### Документация API

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## База данных

### Структура базы данных

- **Водители**: ФИО, дата рождения, позывной, уникальный ID, город, информация о водительском удостоверении, баланс, тариф, таксопарк
- **Автомобили**: Марка, модель, год выпуска, тип КПП, дополнительное оборудование, тариф, гос.номер, VIN номер, тип услуги, фотографии
- **Заказы**: Время, откуда, куда, информация о водителе # wazir_fastapi
