.PHONY: help install run dev docker-build docker-up docker-down migrate lint format test

help:
	@echo "Booking Bot — команды управления"
	@echo ""
	@echo "  make install      — установить зависимости"
	@echo "  make run          — запустить бота"
	@echo "  make docker-build — собрать Docker образ"
	@echo "  make docker-up    — запустить в Docker"
	@echo "  make docker-down  — остановить Docker"
	@echo "  make migrate      — создать новую миграцию"
	@echo "  make lint         — проверить код (ruff)"
	@echo "  make format       — отформатировать код (black)"
	@echo "  make test         — запустить тесты"

install:
	pip install -r requirements.txt

run:
	python -m bot.main

dev:
	PYTHONPATH=. python -m bot.main

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

migrate:
	alembic revision --autogenerate -m "$(msg)"

migrate-up:
	alembic upgrade head

lint:
	ruff check bot/ --fix

format:
	black bot/

test:
	pytest tests/ -v
