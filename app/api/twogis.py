from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Tuple, Optional
from pydantic import BaseModel
import logging

from app.services.twogis_service import twogis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/twogis", tags=["2GIS API"])

@router.get("/geocode")
async def geocode_address(
    address: str = Query(..., description="Адрес для геокодирования"),
    region: str = Query("kg", description="Код региона (kg для Киргизии)")
):
    """
    Геокодирование адреса (преобразование текста в координаты)
    """
    logger.info(f"🔍 Геокодирование адреса: {address}, регион: {region}")
    try:
        result = await twogis_service.geocode_address(address, region=region)
        if result:
            logger.info(f"✅ Адрес успешно геокодирован: {result}")
            return {
                "success": True,
                "data": result
            }
        else:
            logger.warning(f"⚠️ Адрес не найден: {address}")
            raise HTTPException(status_code=404, detail="Адрес не найден")
    except Exception as e:
        logger.error(f"❌ Ошибка геокодирования адреса {address}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка геокодирования: {str(e)}")

@router.get("/reverse-geocode")
async def reverse_geocode(
    lat: float = Query(..., description="Широта"),
    lon: float = Query(..., description="Долгота")
):
    """
    Обратная геокодировка (координаты -> адрес)
    """
    logger.info(f"🔄 Обратная геокодировка: {lat}, {lon}")
    try:
        result = await twogis_service.reverse_geocode(lat, lon)
        if result:
            logger.info(f"✅ Адрес найден: {result}")
            return {
                "success": True,
                "address": result
            }
        else:
            logger.warning(f"⚠️ Адрес не найден для координат: {lat}, {lon}")
            return {
                "success": False,
                "address": f"{lat:.6f}, {lon:.6f}"
            }
    except Exception as e:
        logger.error(f"❌ Ошибка обратной геокодировки {lat}, {lon}: {str(e)}")
        return {
            "success": False,
            "address": f"{lat:.6f}, {lon:.6f}"
        }

@router.get("/search")
async def search_addresses(
    query: str = Query(..., description="Текст для поиска адресов"),
    limit: int = Query(5, description="Максимальное количество результатов"),
    region: str = Query("kg", description="Код региона (kg для Киргизии)")
):
    """
    Поиск адресов с автодополнением
    """
    logger.info(f"🔍 Поиск адресов: {query}, лимит: {limit}, регион: {region}")
    try:
        results = await twogis_service.search_addresses(query, limit=limit, region=region)
        logger.info(f"✅ Найдено адресов: {len(results) if results else 0}")
        return {
            "success": True,
            "data": results
        }
    except Exception as e:
        logger.error(f"❌ Ошибка поиска адресов {query}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка поиска адресов: {str(e)}")

@router.post("/route")
async def get_route(
    origin_lat: float = Query(..., description="Широта точки начала"),
    origin_lon: float = Query(..., description="Долгота точки начала"),
    destination_lat: float = Query(..., description="Широта точки конца"),
    destination_lon: float = Query(..., description="Долгота точки конца"),
    transport_type: str = Query("car", description="Тип транспорта")
):
    """
    Получение маршрута между двумя точками
    """
    logger.info(f"🗺️ Построение маршрута: ({origin_lat}, {origin_lon}) -> ({destination_lat}, {destination_lon}), тип: {transport_type}")
    try:
        origin = (origin_lat, origin_lon)
        destination = (destination_lat, destination_lon)
        
        result = await twogis_service.get_route(origin, destination, transport_type)
        if result:
            logger.info(f"✅ Маршрут построен: расстояние {result.get('distance', 0)}м, время {result.get('duration', 0)}с")
            return {
                "success": True,
                "data": result
            }
        else:
            logger.warning(f"⚠️ Маршрут не найден между точками: {origin} -> {destination}")
            raise HTTPException(status_code=404, detail="Маршрут не найден")
    except Exception as e:
        logger.error(f"❌ Ошибка построения маршрута: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка построения маршрута: {str(e)}")

class DistanceMatrixRequest(BaseModel):
    origins: List[Tuple[float, float]]
    destinations: List[Tuple[float, float]]
    transport_type: str = "car"

@router.post("/distance-matrix")
async def get_distance_matrix(request: DistanceMatrixRequest):
    """
    Получение матрицы расстояний между множественными точками
    """
    try:
        result = await twogis_service.get_distance_matrix(
            request.origins, 
            request.destinations, 
            request.transport_type
        )
        if result:
            return {
                "success": True,
                "data": result
            }
        else:
            raise HTTPException(status_code=404, detail="Матрица расстояний не найдена")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка расчета матрицы расстояний: {str(e)}")

@router.get("/health")
async def health_check():
    """
    Проверка состояния 2GIS API
    """
    return {
        "success": True,
        "api_key_configured": bool(twogis_service.api_key),
        "secret_key_configured": bool(twogis_service.secret_key),
        "status": "ready" if twogis_service.api_key else "no_api_key"
    } 