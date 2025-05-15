#!/usr/bin/env python
"""
Скрипт для запуска миграции базы данных.
Этот скрипт добавляет недостающие столбцы в таблицу drivers.
"""

import sys
import os

# Добавляем путь к проекту в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.migration import run_migrations

if __name__ == "__main__":
    print("Запуск миграции базы данных...")
    try:
        run_migrations()
        print("Миграция успешно выполнена.")
    except Exception as e:
        print(f"Ошибка при выполнении миграции: {str(e)}")
        sys.exit(1)
    sys.exit(0) 