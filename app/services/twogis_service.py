import aiohttp
import asyncio
import hashlib
import base64
import json
import time
import logging
from typing import Dict, List, Tuple, Optional, Any
from app.config import settings

logger = logging.getLogger(__name__)

class TwoGISService:
    """Сервис для работы с 2GIS API"""
    
    def __init__(self):
        self.api_key = settings.TWOGIS_API_KEY
        self.secret_key = settings.TWOGIS_SECRET_KEY
        
        # API endpoints
        self.geocoder_url = settings.TWOGIS_GEOCODER_URL
        self.routing_url = settings.TWOGIS_ROUTING_URL
        self.distance_matrix_url = settings.TWOGIS_DISTANCE_MATRIX_URL
        self.search_url = settings.TWOGIS_SEARCH_URL
        
        # Кэш для геокодирования
        self._geocoding_cache = {}
        self._routing_cache = {}
        
        logger.info(f"🚀 TwoGISService инициализирован с API ключом: {'*' * 8 + self.api_key[-4:] if self.api_key else 'НЕ НАСТРОЕН'}")
        if self.secret_key:
            logger.info(f"🔐 Секретный ключ также настроен")
        else:
            logger.info(f"ℹ️ Секретный ключ не настроен (необязательно)")
    
    def _create_signature(self, data: str) -> str:
        """
        Создание подписи для запросов (если нужен секретный ключ)
        """
        if not self.secret_key:
            return ""
        # Здесь можно добавить логику создания подписи если понадобится
        return ""
    
    async def geocode_address(self, address: str, region: str = "kg") -> Optional[Dict]:
        """
        Геокодирование адреса (преобразование текста в координаты)
        
        Args:
            address: Адрес для поиска
            region: Регион поиска (kg - Киргизия)
        
        Returns:
            Dict с координатами или None
        """
        logger.info(f"🔍 Геокодирование адреса: {address}")
        
        if not self.api_key:
            print("⚠️ 2GIS API ключ не настроен")
            return None
        
        # Проверяем кэш
        cache_key = f"{address}_{region}"
        if cache_key in self._geocoding_cache:
            cache_data = self._geocoding_cache[cache_key]
            if time.time() - cache_data['timestamp'] < settings.GEOCODING_CACHE_TTL:
                logger.info(f"✅ Адрес найден в кэше: {address}")
                return cache_data['data']
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'q': address,
                    'region': region,
                    'fields': 'items.point,items.address_name,items.full_name',
                    'key': self.api_key
                }
                
                logger.debug(f"🌐 Отправка запроса к 2GIS Geocoder API: {params}")
                
                async with session.get(self.geocoder_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.debug(f"📡 Ответ от 2GIS API: {data}")
                        
                        if data.get('result') and data['result'].get('items'):
                            # Берем первый найденный результат
                            item = data['result']['items'][0]
                            result = {
                                'lat': item['point']['lat'],
                                'lon': item['point']['lon'],
                                'address': item.get('full_name', address),
                                'name': item.get('name', ''),
                                'confidence': 1.0
                            }
                            
                            # Сохраняем в кэш
                            self._geocoding_cache[cache_key] = {
                                'data': result,
                                'timestamp': time.time()
                            }
                            
                            logger.info(f"✅ Адрес успешно геокодирован: {result}")
                            return result
                        else:
                            print(f"❌ Адрес не найден: {address}")
                            logger.warning(f"⚠️ Адрес не найден в ответе API: {address}")
                            return None
                    else:
                        print(f"❌ Ошибка геокодирования: {response.status}")
                        logger.error(f"❌ Ошибка API геокодирования: {response.status}")
                        return None
                        
        except Exception as e:
            print(f"❌ Ошибка при геокодировании адреса '{address}': {e}")
            logger.error(f"❌ Ошибка при геокодировании адреса {address}: {e}")
            return None
    
    async def get_route(self, origin: Tuple[float, float], 
                        destination: Tuple[float, float], 
                        transport_type: str = "car") -> Optional[Dict]:
        """
        Получение маршрута между двумя точками
        
        Args:
            origin: Координаты начала (lat, lon)
            destination: Координаты конца (lat, lon)
            transport_type: Тип транспорта (car, taxi, pedestrian)
        
        Returns:
            Dict с информацией о маршруте или None
        """
        if not self.api_key:
            print("⚠️ 2GIS API ключ не настроен")
            return None
        
        # Проверяем кэш
        cache_key = f"{origin}_{destination}_{transport_type}"
        if cache_key in self._routing_cache:
            cache_data = self._routing_cache[cache_key]
            if time.time() - cache_data['timestamp'] < settings.ROUTING_CACHE_TTL:
                return cache_data['data']
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'origin': f"{origin[1]},{origin[0]}",  # lon,lat
                    'destination': f"{destination[1]},{destination[0]}",
                    'type': transport_type,
                    'key': self.api_key
                }
                
                async with session.get(self.routing_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('result') and data['result'].get('routes'):
                            route = data['result']['routes'][0]
                            result = {
                                'distance': route.get('distance', 0),  # в метрах
                                'duration': route.get('duration', 0),  # в секундах
                                'geometry': route.get('geometry', {}),
                                'steps': route.get('steps', []),
                                'transport_type': transport_type
                            }
                            
                            # Сохраняем в кэш
                            self._routing_cache[cache_key] = {
                                'data': result,
                                'timestamp': time.time()
                            }
                            
                            return result
                        else:
                            print(f"❌ Маршрут не найден")
                            return None
                    else:
                        print(f"❌ Ошибка построения маршрута: {response.status}")
                        return None
                        
        except Exception as e:
            print(f"❌ Ошибка при построении маршрута: {e}")
            return None
    
    async def get_distance_matrix(self, origins: List[Tuple[float, float]], 
                                 destinations: List[Tuple[float, float]], 
                                 transport_type: str = "car") -> Optional[Dict]:
        """
        Получение матрицы расстояний и времени
        
        Args:
            origins: Список координат начала
            destinations: Список координат конца
            transport_type: Тип транспорта
        
        Returns:
            Dict с матрицей расстояний и времени
        """
        if not self.api_key:
            print("⚠️ 2GIS API ключ не настроен")
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                # Подготавливаем данные для POST запроса
                payload = {
                    'origins': [{'lat': lat, 'lon': lon} for lat, lon in origins],
                    'destinations': [{'lat': lat, 'lon': lon} for lat, lon in destinations],
                    'type': transport_type,
                    'traffic_mode': 'enabled'  # Учитываем пробки
                }
                
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Key {self.api_key}'
                }
                
                async with session.post(self.distance_matrix_url, 
                                      json=payload, 
                                      headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('result'):
                            return {
                                'distances': data['result'].get('distances', []),
                                'durations': data['result'].get('durations', []),
                                'status': data['result'].get('status', '')
                            }
                        else:
                            print(f"❌ Матрица расстояний не получена")
                            return None
                    else:
                        print(f"❌ Ошибка получения матрицы расстояний: {response.status}")
                        return None
                        
        except Exception as e:
            print(f"❌ Ошибка при получении матрицы расстояний: {e}")
            return None
    
    async def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """
        Обратная геокодировка (координаты -> адрес)
        
        Args:
            lat: Широта
            lon: Долгота
            
        Returns:
            Строка с адресом или None если не найден
        """
        if not self.api_key:
            logger.error("❌ API ключ 2GIS не настроен для обратной геокодировки")
            return None
            
        cache_key = f"reverse_{lat:.6f}_{lon:.6f}"
        
        # Проверяем кэш
        if cache_key in self._geocoding_cache:
            cached_result = self._geocoding_cache[cache_key]
            if time.time() - cached_result['timestamp'] < settings.GEOCODING_CACHE_TTL:
                logger.info(f"🗄️ Возвращаем адрес из кэша: {cached_result['data']}")
                return cached_result['data']
        
        try:
            # Используем геокодер 2GIS для обратного поиска
            params = {
                'point': f"{lon},{lat}",  # 2GIS ожидает lon,lat
                'key': self.api_key,
                'types': 'building,adm_div',
                'radius_m': 100,  # радиус поиска 100 метров
                'output_format': 'json'
            }
            
            async with aiohttp.ClientSession() as session:
                logger.info(f"🔄 Обратная геокодировка через 2GIS API: {lat}, {lon}")
                
                async with session.get(self.geocoder_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('result') and data['result'].get('items'):
                            # Берем первый результат
                            item = data['result']['items'][0]
                            address_name = item.get('full_name', '')
                            
                            if address_name:
                                # Кэшируем результат
                                self._geocoding_cache[cache_key] = {
                                    'data': address_name,
                                    'timestamp': time.time()
                                }
                                
                                logger.info(f"✅ Адрес найден: {address_name}")
                                return address_name
                            else:
                                logger.warning(f"⚠️ Адрес не найден в результатах API")
                                return None
                        else:
                            logger.warning(f"⚠️ Пустой результат от API геокодера")
                            return None
                    else:
                        logger.error(f"❌ HTTP ошибка при обратной геокодировке: {response.status}")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Ошибка обратной геокодировки: {e}")
            return None

    async def search_addresses(self, query: str, region: str = "kg", limit: int = 5) -> List[Dict]:
        """
        Поиск адресов с автодополнением
        
        Args:
            query: Текст для поиска
            region: Регион поиска
            limit: Максимальное количество результатов
        
        Returns:
            Список найденных адресов
        """
        if not self.api_key:
            print("⚠️ 2GIS API ключ не настроен")
            return []
        
        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'q': query,
                    'region': region,
                    'fields': 'items.point,items.address_name,items.full_name,items.name',
                    'key': self.api_key,
                    'limit': limit
                }
                
                async with session.get(self.geocoder_url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data.get('result') and data['result'].get('items'):
                            results = []
                            for item in data['result']['items']:
                                results.append({
                                    'lat': item['point']['lat'],
                                    'lon': item['point']['lon'],
                                    'address': item.get('full_name', ''),
                                    'name': item.get('name', ''),
                                    'short_address': item.get('address_name', '')
                                })
                            return results
                        else:
                            return []
                    else:
                        print(f"❌ Ошибка поиска адресов: {response.status}")
                        return []
                        
        except Exception as e:
            print(f"❌ Ошибка при поиске адресов: {e}")
            return []

# Создаем экземпляр сервиса
twogis_service = TwoGISService() 