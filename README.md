# CrowdSec WebUI

Минимальный WebUI для базового управления блокировками CrowdSec через официальный LAPI.

## Что умеет

- Просмотр активных решений (`/v1/decisions`)
- Сводка метрик CrowdSec из `/metrics` (аналогично `cscli metrics`)
- Фильтрация по `scope`, `value`, `type`, `origin`, `scenario`, `limit`
- Ручное добавление блокировки (`POST /v1/alerts`, manual alert)
- Удаление блокировки по `id` (`DELETE /v1/decisions/{id}`)

## Требования

- Доступ к CrowdSec Local API (LAPI)
- Ключ bouncer API (для чтения)
- Machine login/password (для создания и удаления решений через UI)

Получить bouncer key:

```bash
cscli bouncers add crowdsec-webui
```

Получить machine credentials:

```bash
cscli machines add crowdsec-webui
```

## Быстрый старт в Docker

1. Создать env-файл:

```bash
cp .env.example .env
```

2. Заполнить в `.env`:
- `CROWDSEC_API_KEY` для просмотра решений
- `CROWDSEC_MACHINE_LOGIN` и `CROWDSEC_MACHINE_PASSWORD` для ручного create/delete

3. Запустить:

```bash
docker compose up --build -d
```

4. Открыть UI:

- `http://localhost:${WEB_PORT}` (по умолчанию `http://localhost:8088`)

## Конфигурация

- `CROWDSEC_API_URL` - URL CrowdSec LAPI, по умолчанию `http://crowdsec:8080`
- `CROWDSEC_METRICS_URL` - явный URL Prometheus-метрик CrowdSec (например `http://crowdsec:6060/metrics`), если не задан, UI пробует `${CROWDSEC_API_URL}/metrics`
- `CROWDSEC_API_KEY` - ключ bouncer (read-only)
- `CROWDSEC_MACHINE_LOGIN` - логин machine-пользователя LAPI (write-операции)
- `CROWDSEC_MACHINE_PASSWORD` - пароль machine-пользователя LAPI (write-операции)
- `HTTP_TIMEOUT` - timeout HTTP-запросов в секундах, по умолчанию `10`
- `WEB_PORT` - порт публикации WebUI на хосте, по умолчанию `8088`

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
