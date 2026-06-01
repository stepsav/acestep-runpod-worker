# Serverless-воркер ACE-Step 1.5 поверх готового образа с моделями.
# Готовый образ уже содержит acestep + зависимости + веса (~15 ГБ).
FROM valyriantech/ace-step-1.5:latest

# Ставим RunPod SDK ИМЕННО в тот python, которым будет запускаться handler
# (в образе может быть несколько окружений — обычный pip мог поставить не туда).
RUN python -m pip install --no-cache-dir runpod

# Проверка при сборке: если runpod не импортируется этим python — сборка упадёт
# с понятной ошибкой в Build logs (а не молча в рантайме).
RUN python -c "import runpod; print('RUNPOD OK', runpod.__version__)"

# Наш обработчик
WORKDIR /app
COPY handler.py /app/handler.py

# Сбрасываем ENTRYPOINT базового образа, иначе наш CMD не выполнится.
ENTRYPOINT []

# Запускаем через sh, перенаправляя stderr→stdout, чтобы трейсбэки попадали в логи RunPod.
CMD ["sh", "-c", "python -u /app/handler.py 2>&1"]
