# CrowdSec WebUI

Минимальный WebUI для базового управления блокировками CrowdSec через официальный LAPI.

## Что умеет

- Просмотр активных решений (`/v1/decisions`)
- Фильтрация по `scope`, `value`, `type`, `limit`
- Ручное добавление блокировки (`POST /v1/decisions`)
- Удаление блокировки по `id` (`DELETE /v1/decisions/{id}`)

## Требования

- Доступ к CrowdSec Local API (LAPI)
- Ключ bouncer API

Получить ключ можно так:

```bash
cscli bouncers add crowdsec-webui
```

## Быстрый старт в Docker

1. Создать env-файл:

```bash
cp .env.example .env
```

2. Заполнить `CROWDSEC_API_KEY` в `.env`.

3. Запустить:

```bash
docker compose up --build -d
```

4. Открыть UI:

- `http://localhost:8081`

## Конфигурация

- `CROWDSEC_API_URL` - URL CrowdSec LAPI, по умолчанию `http://crowdsec:8080`
- `CROWDSEC_API_KEY` - ключ bouncer (обязательно)
- `HTTP_TIMEOUT` - timeout HTTP-запросов в секундах, по умолчанию `10`

## Локальный запуск (без Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export CROWDSEC_API_URL=http://localhost:8080
export CROWDSEC_API_KEY=<your-key>
uvicorn app.main:app --reload --port 8080
```

## Важные замечания

- UI работает через backend-прокси и не хранит ключ в браузере.
- Для production рекомендуется ограничить доступ к UI (например, reverse proxy + auth).
