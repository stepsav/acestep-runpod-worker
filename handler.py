"""
RunPod Serverless handler для ACE-Step 1.5 — МАКСИМАЛЬНОЕ КАЧЕСТВО.
Модели: acestep-v15-xl-sft (4B DiT) + acestep-5Hz-lm-4B (заданы env в Dockerfile).

Модели грузятся лениво при первом запросе; любая ошибка возвращается в ответе
(поля "error"/"traceback"), чтобы её было видно во вкладке Requests.

Вход (event["input"]):
  lyrics    — текст песни (метки [Verse]/[Chorus]; ударения в словах помогают произношению)
  tags      — стиль/жанр (caption), напр. "pop, clear vocals, 120 bpm, male vocal"
  duration  — длительность в секундах (по умолч. 30)
  language  — язык вокала, по умолч. "ru"
  bpm       — темп (опционально)
  seed      — для повторяемости/вариаций (опционально)
  infer_steps    — число шагов инференса, больше = качественнее/медленнее (опционально)
  guidance_scale — насколько строго следовать стилю/тексту (опционально)

Доп. параметры применяются только если их поддерживает текущая версия модели
(иначе тихо игнорируются — воркер не падает).
"""
import os
import base64
import inspect
import traceback

import runpod

# Топ-качество по умолчанию (переопределяется env в Dockerfile).
CHECKPOINTS = os.environ.get("ACESTEP_CHECKPOINTS", "/app/checkpoints")
DIT_CONFIG = os.environ.get("ACESTEP_CONFIG_PATH", "/app/checkpoints/acestep-v15-xl-sft")
LM_MODEL = os.environ.get("ACESTEP_LM_MODEL_PATH", "/app/checkpoints/acestep-5Hz-lm-4B")
PROJECT_ROOT = os.environ.get("ACESTEP_PROJECT_ROOT", "/app")
LM_BACKEND = os.environ.get("ACESTEP_LM_BACKEND", "vllm")
SAVE_DIR = "/tmp/acestep_out"

_STATE = {"ready": False, "error": None, "dit": None, "llm": None, "mod": None}


def _accepted_kwargs(callable_obj, kwargs):
    """Оставляем только те kwargs, которые принимает данная функция/класс."""
    try:
        valid = set(inspect.signature(callable_obj).parameters)
        return {k: v for k, v in kwargs.items() if k in valid}
    except (ValueError, TypeError):
        return kwargs


def _load_models():
    if _STATE["ready"] or _STATE["error"]:
        return
    try:
        from acestep.handler import AceStepHandler
        from acestep.llm_inference import LLMHandler
        from acestep import inference as ace_inf

        print(f"[ACE-Step] DiT={DIT_CONFIG} LM={LM_MODEL}", flush=True)
        print("[ACE-Step] Загружаю DiT handler…", flush=True)
        dit = AceStepHandler()
        dit.initialize_service(project_root=PROJECT_ROOT, config_path=DIT_CONFIG, device="cuda")

        print("[ACE-Step] Загружаю LLM handler…", flush=True)
        llm = LLMHandler()
        llm.initialize(checkpoint_dir=CHECKPOINTS, lm_model_path=LM_MODEL, backend=LM_BACKEND, device="cuda")

        _STATE.update(dit=dit, llm=llm, mod=ace_inf, ready=True)
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

        # Pass-through: принимаем ЛЮБЫЕ поля ACE-Step. Дружелюбные псевдонимы маппим
        # на реальные имена, остальное идёт как есть. Несуществующие поля отфильтруются.
        mapped = dict(inp)
        if "tags" in mapped:
            mapped.setdefault("caption", mapped.pop("tags"))
        if "language" in mapped:
            mapped.setdefault("vocal_language", mapped.pop("language"))

        # Разумные значения по умолчанию (если бот не прислал)
        mapped.setdefault("task_type", "text2music")
        mapped.setdefault("vocal_language", "ru")

        # Раздаём поля по тем классам, что их принимают (лишнее отфильтруется)
        params = GenerationParams(**_accepted_kwargs(GenerationParams, mapped))
        config = GenerationConfig(
            **_accepted_kwargs(GenerationConfig, {"batch_size": 1, "audio_format": "mp3", **mapped})
        )

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
