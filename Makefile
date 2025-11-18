COMPOSE ?= docker compose
APP_SERVICE ?= app

.PHONY: help full build up down stop restart logs ps shell \
        migrate-head migrate-tail migrate-up migrate-down \
        migrate-up-% migrate-down-% migrate-status \
        test lint format

.DEFAULT_GOAL := help

help: ## Показывает список команд
	@echo "Available targets:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS=":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

full: build migrate-head up ## Собрать образы и поднять все сервисы в фоне
	@echo "Stack is up ✅"

build: ## Собрать docker-образы
	$(COMPOSE) build

up: ## Запустить контейнеры в фоне
	$(COMPOSE) up -d

down: ## Остановить и удалить контейнеры, сети и т.п.
	$(COMPOSE) down

stop: ## Остановить контейнеры (без удаления)
	$(COMPOSE) stop

restart: down up ## Перезапуск всего стека

logs: ## Логи всех сервисов (follow)
	$(COMPOSE) logs -f

ps: ## Список контейнеров в стеке
	$(COMPOSE) ps

shell: ## Открыть bash внутри app-контейнера
	$(COMPOSE) exec $(APP_SERVICE) bash

migrate-head: ## Alembic: upgrade до head
	$(COMPOSE) run --rm $(APP_SERVICE) alembic upgrade head

migrate-tail: ## Alembic: downgrade до base (самый первый)
	$(COMPOSE) run --rm $(APP_SERVICE) alembic downgrade base

migrate-up: ## Alembic: upgrade на 1 шаг
	$(COMPOSE) run --rm $(APP_SERVICE) alembic upgrade +1

migrate-down: ## Alembic: downgrade на 1 шаг
	$(COMPOSE) run --rm $(APP_SERVICE) alembic downgrade -1

migrate-up-%: ## Alembic: upgrade на N шагов (make migrate-up-2)
	$(COMPOSE) run --rm $(APP_SERVICE) alembic upgrade +$*

migrate-down-%: ## Alembic: downgrade на N шагов (make migrate-down-3)
	$(COMPOSE) run --rm $(APP_SERVICE) alembic downgrade -$*

migrate-status: ## Показать текущее состояние миграций
	$(COMPOSE) run --rm $(APP_SERVICE) alembic current

test: ## Запуск тестов внутри app-контейнера
	$(COMPOSE) run --rm $(APP_SERVICE) sh -c "pytest"

lint: ## Линтеры (ruff по умолчанию)
	$(COMPOSE) run --rm $(APP_SERVICE) sh -c "ruff check ."

format: ## Форматирование кода (isort + black)
	$(COMPOSE) run --rm $(APP_SERVICE) sh -c "isort . && black ."
