# Serverless-воркер ACE-Step 1.5 поверх готового образа с моделями.
# Готовый образ уже содержит acestep + зависимости + веса (~15 ГБ).
FROM valyriantech/ace-step-1.5:latest

# RunPod serverless SDK
RUN pip install --no-cache-dir runpod

# Наш обработчик
WORKDIR /app
COPY handler.py /app/handler.py

# ВАЖНО: у базового образа есть свой ENTRYPOINT (запуск их FastAPI/сервиса).
# Сбрасываем его, иначе наш CMD не выполнится и воркер упадёт с кодом 1.
ENTRYPOINT []

# В serverless главный процесс — наш handler-цикл
CMD ["python", "-u", "/app/handler.py"]
