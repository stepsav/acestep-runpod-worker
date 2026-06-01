# Serverless-воркер ACE-Step 1.5 — МАКСИМАЛЬНОЕ КАЧЕСТВО (XL-sft 4B + LM 4B).
# Базовый образ содержит код acestep + базовые модели; поверх докачиваем топ-чекпойнты.
FROM valyriantech/ace-step-1.5:latest

# RunPod SDK + huggingface_hub (в тот же python, которым запускаем handler)
RUN python -m pip install --no-cache-dir runpod huggingface_hub

# Лучшее качество: XL-sft (4B DiT, "Very High") + 4B языковая модель (точные слова).
# Качаем чекпойнты прямо в образ при сборке (~20 ГБ).
RUN python -c "from huggingface_hub import snapshot_download as d; d('ACE-Step/acestep-v15-xl-sft', local_dir='/app/checkpoints/acestep-v15-xl-sft'); d('ACE-Step/acestep-5Hz-lm-4B', local_dir='/app/checkpoints/acestep-5Hz-lm-4B'); print('CHECKPOINTS DOWNLOADED')"

# Указываем воркеру использовать именно топ-чекпойнты
ENV ACESTEP_CONFIG_PATH=/app/checkpoints/acestep-v15-xl-sft
ENV ACESTEP_LM_MODEL_PATH=/app/checkpoints/acestep-5Hz-lm-4B

# Проверка при сборке: runpod импортируется этим python
RUN python -c "import runpod; print('RUNPOD OK', runpod.__version__)"

WORKDIR /app
COPY handler.py /app/handler.py

# Сбрасываем ENTRYPOINT базового образа + stderr→stdout, чтобы ошибки были видны в логах
ENTRYPOINT []
CMD ["sh", "-c", "python -u /app/handler.py 2>&1"]
