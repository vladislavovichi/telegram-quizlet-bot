COMPOSE ?= docker compose
APP_SERVICE ?= app
NEURAL_SERVICE ?= neuralnet

.PHONY: help full build build-no-cache build-app build-neural \
        up up-app up-neural down stop stop-app stop-neural \
        restart restart-app restart-neural \
        logs logs-app neural-logs ps shell neural-shell \
        migrate-head migrate-tail migrate-up migrate-down \
        migrate-up-% migrate-down-% migrate-status \
        test lint format

.DEFAULT_GOAL := help

help: ## Показывает список команд
	@echo "Доступные команды:"
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS=":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

full: build migrate-head up ## Собрать образы и поднять все сервисы в фоне
	@echo "Stack is up ✅"

build: ## Собрать docker-образы всех сервисов с build:
	$(COMPOSE) build

build-no-cache: ## Собрать docker-образы всех сервисов с build без кеша:
	$(COMPOSE) build --no-cache

build-app: ## Собрать образ только для app-сервиса
	$(COMPOSE) build $(APP_SERVICE)

build-neural: ## Собрать образ только для neuralnet-сервиса
	$(COMPOSE) build $(NEURAL_SERVICE)

up: ## Запустить все контейнеры в фоне
	$(COMPOSE) up -d

up-neural: ## Запустить только neuralnet-сервис
	$(COMPOSE) up -d $(NEURAL_SERVICE)

down: ## Остановить и удалить контейнеры, сети и т.п.
	$(COMPOSE) down

stop: ## Остановить все контейнеры (без удаления)
	$(COMPOSE) stop

stop-app: ## Остановить только app-сервис
	$(COMPOSE) stop $(APP_SERVICE)

stop-neural: ## Остановить только neuralnet-сервис
	$(COMPOSE) stop $(NEURAL_SERVICE)

restart: down up ## Перезапуск всего стека

restart-app: stop-app up-app ## Перезапуск только app-сервиса

restart-neural: stop-neural up-neural ## Перезапуск только neuralnet-сервиса

logs: ## Логи всех сервисов (follow)
	$(COMPOSE) logs -f

logs-app: ## Логи только app-сервиса
	$(COMPOSE) logs -f $(APP_SERVICE)

logs-neural: ## Логи только neuralnet-сервиса
	$(COMPOSE) logs -f $(NEURAL_SERVICE)

ps: ## Список контейнеров в стеке
	$(COMPOSE) ps

shell: ## Открыть bash внутри app-контейнера
	$(COMPOSE) exec $(APP_SERVICE) bash

shell-neural: ## Открыть bash внутри neuralnet-контейнера
	$(COMPOSE) exec $(NEURAL_SERVICE) bash

migrate-head: ## Alembic: upgrade до head
	$(COMPOSE) run --rm $(APP_SERVICE) alembic -c config/alembic.ini upgrade head

migrate-tail: ## Alembic: downgrade до base (самый первый)
	$(COMPOSE) run --rm $(APP_SERVICE) alembic -c config/alembic.ini downgrade base

migrate-up: ## Alembic: upgrade на 1 шаг
	$(COMPOSE) run --rm $(APP_SERVICE) alembic -c config/alembic.ini upgrade +1

migrate-down: ## Alembic: downgrade на 1 шаг
	$(COMPOSE) run --rm $(APP_SERVICE) alembic -c config/alembic.ini downgrade -1

migrate-up-%: ## Alembic: upgrade на N шагов (make migrate-up-2)
	$(COMPOSE) run --rm $(APP_SERVICE) alembic -c config/alembic.ini upgrade +$*

migrate-down-%: ## Alembic: downgrade на N шагов (make migrate-down-3)
	$(COMPOSE) run --rm $(APP_SERVICE) alembic -c config/alembic.ini downgrade -$*

migrate-status: ## Показать текущее состояние миграций
	$(COMPOSE) run --rm $(APP_SERVICE) alembic -c config/alembic.ini current

test: ## Запуск тестов внутри app-контейнера
	$(COMPOSE) run --rm $(APP_SERVICE) sh -c "pytest -c config/pytest.ini"

lint: ## Линтеры (ruff по умолчанию)
	$(COMPOSE) run --rm $(APP_SERVICE) sh -c "ruff check ."

format: ## Форматирование кода (isort + black)
	$(COMPOSE) run --rm $(APP_SERVICE) sh -c "isort . && black ."
