"""
RunPod Serverless handler для ACE-Step 1.5 (генерация песни из текста + стиль).

Собирается ПОВЕРХ готового образа valyriantech/ace-step-1.5:latest,
в котором модели (~15 ГБ) и зависимости уже предустановлены.

Особенность: модели грузятся ЛЕНИВО при первом запросе, а любая ошибка
импорта/инициализации возвращается прямо в ответе (поле "error"/"traceback"),
чтобы её было видно во вкладке Requests, а не только в логах.

Вход (event["input"]):
  lyrics    — текст песни (можно с метками [Verse]/[Chorus])
  tags      — стиль/жанр (caption), напр. "pop, energetic, 120 bpm, male vocal"
  duration  — длительность в секундах (по умолч. 30)
  language  — язык вокала, по умолч. "ru"
  bpm       — темп (опционально)

Выход:
  audio_base64 (mp3 в base64), format, sample_rate, seed
  либо error + traceback при сбое.
"""
import os
import base64
import traceback

import runpod

# Пути к моделям внутри готового образа (можно переопределить env'ом endpoint'а).
CHECKPOINTS = os.environ.get("ACESTEP_CHECKPOINTS", "/app/checkpoints")
DIT_CONFIG = os.environ.get("ACESTEP_CONFIG_PATH", "/app/checkpoints/acestep-v15-base")
LM_MODEL = os.environ.get("ACESTEP_LM_MODEL_PATH", "/app/checkpoints/acestep-5Hz-lm-1.7B")
PROJECT_ROOT = os.environ.get("ACESTEP_PROJECT_ROOT", "/app")
LM_BACKEND = os.environ.get("ACESTEP_LM_BACKEND", "vllm")
SAVE_DIR = "/tmp/acestep_out"

# Глобальное состояние моделей (ленивая загрузка один раз).
_STATE = {"ready": False, "error": None, "dit": None, "llm": None, "mod": None}


def _load_models():
    """Грузим модели один раз. Ошибку сохраняем, не роняя процесс."""
    if _STATE["ready"] or _STATE["error"]:
        return
    try:
        from acestep.handler import AceStepHandler
        from acestep.llm_inference import LLMHandler
        from acestep import inference as ace_inf

        print("[ACE-Step] Загружаю DiT handler…", flush=True)
        dit = AceStepHandler()
        dit.initialize_service(project_root=PROJECT_ROOT, config_path=DIT_CONFIG, device="cuda")

        print("[ACE-Step] Загружаю LLM handler…", flush=True)
        llm = LLMHandler()
        llm.initialize(
            checkpoint_dir=CHECKPOINTS,
            lm_model_path=LM_MODEL,
            backend=LM_BACKEND,
            device="cuda",
        )

        _STATE["dit"] = dit
        _STATE["llm"] = llm
        _STATE["mod"] = ace_inf
        _STATE["ready"] = True
        print("[ACE-Step] Модели готовы.", flush=True)
    except Exception:
        _STATE["error"] = traceback.format_exc()
        print("[ACE-Step] ОШИБКА загрузки моделей:\n" + _STATE["error"], flush=True)


def handler(event):
    try:
        _load_models()
        if _STATE["error"]:
            return {"error": "model load failed", "traceback": _STATE["error"]}

        ace_inf = _STATE["mod"]
        GenerationParams = ace_inf.GenerationParams
        GenerationConfig = ace_inf.GenerationConfig
        generate_music = ace_inf.generate_music

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
        result = generate_music(_STATE["dit"], _STATE["llm"], params, config, save_dir=SAVE_DIR)

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
    except Exception:
        return {"error": "handler crashed", "traceback": traceback.format_exc()}


runpod.serverless.start({"handler": handler})
