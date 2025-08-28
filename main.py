#!/usr/bin/env python3
"""
Точка входа в приложение WAZIR MTT API
"""

if __name__ == "__main__":
    import uvicorn
    
    # Запускаем FastAPI приложение
    print("🚀 Запуск WAZIR MTT API сервера...")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)