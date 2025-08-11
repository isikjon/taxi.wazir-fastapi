import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Отладочная информация
print(f"🔧 config.py: Загружаем переменные окружения...")
print(f"🔧 config.py: TWOGIS_API_KEY из os.getenv: {repr(os.getenv('TWOGIS_API_KEY'))}")

class Settings:
    # 2GIS API Configuration
    TWOGIS_API_KEY = os.getenv("TWOGIS_API_KEY")  # Берем из .env файла
    TWOGIS_SECRET_KEY = os.getenv("TWOGIS_SECRET_KEY", "")  # Опциональный
    
    # 2GIS API Endpoints
    TWOGIS_GEOCODER_URL = "https://catalog.api.2gis.com/3.0/items/geocode"
    TWOGIS_ROUTING_URL = "https://routing.api.2gis.com/routing/2.0/route"
    TWOGIS_DISTANCE_MATRIX_URL = "https://routing.api.2gis.com/routing/2.0/distancematrix"
    TWOGIS_SEARCH_URL = "https://catalog.api.2gis.com/3.0/items/search"
    
    # Default coordinates for Kyrgyzstan (Osh city center)
    DEFAULT_LAT = 40.5138
    DEFAULT_LON = 72.8019
    
    # API request limits
    MAX_GEOCODING_REQUESTS = 1000  # per day
    MAX_ROUTING_REQUESTS = 1000    # per day
    
    # Cache settings
    GEOCODING_CACHE_TTL = 3600  # 1 hour in seconds
    ROUTING_CACHE_TTL = 1800    # 30 minutes in seconds

settings = Settings()

# Отладочная информация после создания объекта
print(f"🔧 config.py: settings.TWOGIS_API_KEY = {repr(settings.TWOGIS_API_KEY)}")
print(f"🔧 config.py: Инициализация завершена") 