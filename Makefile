.PHONY: help build up down logs clean restart shell db-shell test

help: ## Показать справку
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Собрать Docker образ
	docker-compose build

up: ## Запустить все сервисы
	docker-compose up -d

down: ## Остановить все сервисы
	docker-compose down

logs: ## Показать логи
	docker-compose logs -f

clean: ## Очистить все контейнеры и образы
	docker-compose down -v --rmi all
	docker system prune -f

restart: ## Перезапустить сервисы
	docker-compose restart

shell: ## Войти в контейнер приложения
	docker-compose exec app bash

db-shell: ## Войти в контейнер базы данных
	docker-compose exec db psql -U wazir_user -d wazir_db

test: ## Запустить тесты
	docker-compose exec app python -m pytest

migrate: ## Запустить миграции
	docker-compose exec app alembic upgrade head

create-migration: ## Создать новую миграцию
	docker-compose exec app alembic revision --autogenerate -m "$(message)"

status: ## Показать статус сервисов
	docker-compose ps

volumes: ## Показать тома
	docker volume ls

networks: ## Показать сети
	docker network ls
