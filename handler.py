"""
RunPod Serverless handler для ACE-Step 1.5 (генерация песни из текста + стиль).

Собирается ПОВЕРХ готового образа valyriantech/ace-step-1.5:latest,
в котором модели (~15 ГБ) и зависимости уже предустановлены.

Вход (event["input"]):
  lyrics    — текст песни (строка, можно с метками [Verse]/[Chorus])
  tags      — стиль/жанр (caption), напр. "pop, energetic, 120 bpm, male vocal"
  duration  — длительность в секундах (по умолч. 30)
  language  — язык вокала, по умолч. "ru" (русский!)
  bpm       — темп (опционально)

Выход:
  audio_base64 — mp3 в base64
  format, sample_rate, seed
"""
import os
import base64
import traceback

import runpod

from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams, GenerationConfig, generate_music

# Пути к моделям внутри готового образа (значения по умолчанию из его документации).
# Можно переопределить переменными окружения в настройках endpoint'а.
CHECKPOINTS = os.environ.get("ACESTEP_CHECKPOINTS", "/app/checkpoints")
DIT_CONFIG = os.environ.get("ACESTEP_CONFIG_PATH", "/app/checkpoints/acestep-v15-base")
LM_MODEL = os.environ.get("ACESTEP_LM_MODEL_PATH", "/app/checkpoints/acestep-5Hz-lm-1.7B")
PROJECT_ROOT = os.environ.get("ACESTEP_PROJECT_ROOT", "/app")
LM_BACKEND = os.environ.get("ACESTEP_LM_BACKEND", "vllm")
SAVE_DIR = "/tmp/acestep_out"

# --- Загрузка моделей один раз при холодном старте воркера ---
print("[ACE-Step] Загружаю DiT handler…", flush=True)
dit_handler = AceStepHandler()
dit_handler.initialize_service(project_root=PROJECT_ROOT, config_path=DIT_CONFIG, device="cuda")

print("[ACE-Step] Загружаю LLM handler…", flush=True)
llm_handler = LLMHandler()
llm_handler.initialize(
    checkpoint_dir=CHECKPOINTS,
    lm_model_path=LM_MODEL,
    backend=LM_BACKEND,
    device="cuda",
)
print("[ACE-Step] Модели готовы. Жду запросы.", flush=True)


def handler(event):
    try:
        inp = event.get("input", {}) or {}
        lyrics = inp.get("lyrics", "")
        tags = inp.get("tags") or inp.get("caption") or "pop"
        duration = int(inp.get("duration", 30))
        language = inp.get("language", "ru")
        bpm = inp.get("bpm")

        kwargs = dict(
            task_type="text2music",
            caption=tags,
            lyrics=lyrics,
            vocal_language=language,
            duration=duration,
        )
        if bpm:
            kwargs["bpm"] = int(bpm)

        params = GenerationParams(**kwargs)
        config = GenerationConfig(batch_size=1, audio_format="mp3")

        os.makedirs(SAVE_DIR, exist_ok=True)
        result = generate_music(dit_handler, llm_handler, params, config, save_dir=SAVE_DIR)

        if not getattr(result, "success", False):
            return {"error": getattr(result, "error", "generation failed")}

        audio = result.audios[0]
        with open(audio["path"], "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        return {
            "audio_base64": b64,
            "format": "mp3",
            "sample_rate": audio.get("sample_rate"),
            "seed": audio.get("params", {}).get("seed"),
        }
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}


runpod.serverless.start({"handler": handler})
