from typing import Literal
import os

ModelType = Literal[
    "text",
    "vision",
    "code"
]

DEFAULT_TEXT_MODEL = "qwen2.5:3b"
DEFAULT_VISION_MODEL = "qwen2.5vl:3b"
_DETECTED_CODE_MODEL = None


def get_installed_code_model() -> str:
    """
    Check if a dedicated local coding model is installed in Ollama.
    Falls back to qwen2.5:3b if none is found.
    Never calls external APIs.
    """
    global _DETECTED_CODE_MODEL
    if _DETECTED_CODE_MODEL is not None:
        return _DETECTED_CODE_MODEL

    try:
        import ollama
        models_info = ollama.list()
        installed_names = [
            (m.get("model") or m.get("name") or "").lower()
            for m in models_info.get("models", [])
        ]
        for name in installed_names:
            if "coder" in name or "deepseek-coder" in name:
                _DETECTED_CODE_MODEL = name
                return _DETECTED_CODE_MODEL
    except Exception:
        pass

    _DETECTED_CODE_MODEL = DEFAULT_TEXT_MODEL
    return _DETECTED_CODE_MODEL


def select_model(task: str) -> str:
    """
    Select a local model type based on the type of task.
    Returns: 'vision', 'code', or 'text'
    """
    task = (task or "").lower()

    # Vision-related tasks
    if any(word in task for word in [
        "image",
        "photo",
        "picture",
        "drawing",
        "diagram",
        "scanned",
        "handwritten",
        "visible",
        "see in the",
        "show"
    ]):
        return "vision"

    # Coding-related tasks
    if any(word in task for word in [
        "code",
        "python",
        "program",
        "debug",
        "function",
        "script",
        "run python"
    ]):
        return "code"

    # Default: normal text task
    return "text"


def get_model_for_task(task_type: str) -> str:
    """
    Return the confirmed installed Ollama model string for a given task type.
    """
    if task_type == "vision":
        return DEFAULT_VISION_MODEL
    elif task_type == "code":
        return get_installed_code_model()
    else:
        return DEFAULT_TEXT_MODEL