# Serverless-воркер ACE-Step 1.5 поверх готового образа с моделями.
# Готовый образ уже содержит acestep + зависимости + веса (~15 ГБ),
# поэтому нам остаётся добавить только RunPod SDK и наш handler.
FROM valyriantech/ace-step-1.5:latest

# RunPod serverless SDK
RUN pip install --no-cache-dir runpod

# Наш обработчик
WORKDIR /app
COPY handler.py /app/handler.py

# В serverless главный процесс — это наш handler-цикл
CMD ["python", "-u", "/app/handler.py"]
