# ACE-Step 1.5 — Serverless-воркер для RunPod (pay-per-use)

Генерация песни из текста + стиля. Вокал на русском (`language: "ru"`).
Собирается поверх готового образа `valyriantech/ace-step-1.5` (модели уже внутри),
поэтому сборка быстрая, а холодный старт — только загрузка моделей в GPU.

## Файлы
- `handler.py` — RunPod serverless обработчик (вход/выход см. внутри файла)
- `Dockerfile` — образ = готовый ACE-Step + runpod SDK + наш handler
- `test_input.json` — пример запроса (русская песня)
- `hub.json` — метаданные

---

## Деплой через GitHub (без локального Docker)

### 1. Создай репозиторий на GitHub
- Новый репозиторий (можно приватный), напр. `acestep-runpod-worker`.
- Залей в него содержимое папки `worker-acestep/` (handler.py, Dockerfile, test_input.json, hub.json).
  - Через сайт GitHub: «Add file → Upload files» — просто перетащи файлы.
  - Или через git, если умеешь.

### 2. Подключи GitHub к RunPod
- RunPod → **Settings → Connections** → подключить GitHub-аккаунт (один раз).

### 3. Создай Serverless endpoint из репозитория
- RunPod → **Serverless → New Endpoint**.
- Источник: **GitHub Repo** → выбери свой `acestep-runpod-worker`, ветку `main`.
- RunPod найдёт `Dockerfile` и **сам соберёт образ** (первая сборка 5–15 мин).

### 4. Настройки endpoint
- **GPU: 32 ГБ+** (RTX 5090 32GB / A100 / L40S). ⚠️ 24 ГБ (4090) НЕ хватит —
  образ держит base-DiT + 1.7B LM.
- **Min Workers: 0** ← плата только за запросы (pay-per-use).
- **Max Workers: 2–3**, **Idle Timeout: 60–120 c**, **FlashBoot: ON**.
- Container Disk: **60 ГБ** (модели ~15 ГБ + место).
- (env уже зашиты в образ; при желании переопредели `ACESTEP_CONFIG_PATH` / `ACESTEP_LM_MODEL_PATH`.)
- **Deploy** → запиши **Endpoint ID** → в `.env` бота как `RUNPOD_ENDPOINT_ACESTEP`.

### 5. Тест
В консоли endpoint (вкладка **Requests/Test**) вставь содержимое `test_input.json` → **Run**.
Первый запрос — cold start (загрузка моделей, 1–3 мин). В ответ придёт `audio_base64`.

Или с компа:
```powershell
$env:RUNPOD_API_KEY="ключ"
$env:RUNPOD_ENDPOINT_ID="id_эндпоинта"
python ../tools/test_runpod.py   # поменяй PAYLOAD на содержимое test_input.json
```

---

## Если сборка/запуск упадёт
Это нормально для кастомного воркера — смотрим логи RunPod (вкладка **Logs** у endpoint):
- ошибки импорта `acestep.*` → уточним пути/имена в образе;
- `initialize` ругается на аргументы → подправим сигнатуру под конкретную версию;
- не хватает VRAM → берём GPU побольше или переключаем на turbo-модель.
Присылай текст ошибки из логов — поправлю handler.
