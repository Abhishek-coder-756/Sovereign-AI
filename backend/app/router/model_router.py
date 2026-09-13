from typing import Literal

import ollama


# =========================================================
# MODEL TYPES
# =========================================================

ModelType = Literal[
    "text",
    "vision",
    "code"
]


# =========================================================
# DEFAULT MODELS
# =========================================================

DEFAULT_TEXT_MODEL = "qwen2.5:3b"
DEFAULT_VISION_MODEL = "qwen2.5vl:3b"

_DETECTED_CODE_MODEL = None


# =========================================================
# DETECT CODE MODEL
# =========================================================

def get_installed_code_model() -> str:
    """
    Detect a dedicated local coding model installed
    in Ollama.

    If no coding model exists, use the normal local
    text model.

    No external API is used.
    """

    global _DETECTED_CODE_MODEL

    if _DETECTED_CODE_MODEL is not None:
        return _DETECTED_CODE_MODEL

    try:

        models_info = ollama.list()

        installed_names = []

        for model in models_info.get("models", []):

            name = (
                model.get("model")
                or model.get("name")
                or ""
            )

            if name:
                installed_names.append(
                    name.lower()
                )

        # Prefer dedicated coding models
        for name in installed_names:

            if (
                "coder" in name
                or "deepseek-coder" in name
            ):

                _DETECTED_CODE_MODEL = name

                return _DETECTED_CODE_MODEL

    except Exception:

        pass

    # No dedicated coding model found
    _DETECTED_CODE_MODEL = DEFAULT_TEXT_MODEL

    return _DETECTED_CODE_MODEL


# =========================================================
# SELECT MODEL TYPE
# =========================================================

def select_model(task: str) -> ModelType:
    """
    Determine the type of model required.

    Returns:
        vision
        code
        text
    """

    task = (task or "").lower().strip()

    # =====================================================
    # VISION
    # =====================================================

    vision_keywords = [
        "image",
        "photo",
        "picture",
        "drawing",
        "diagram",
        "scanned",
        "handwritten",
        "visual",
        "visible",
        "look at",
        "look in",
        "see in",
        "what do you see",
        "what can you see",
        "what is shown",
        "what does this show"
    ]

    if any(
        keyword in task
        for keyword in vision_keywords
    ):

        return "vision"

    # =====================================================
    # CODE
    # =====================================================

    code_keywords = [
        "code",
        "python",
        "program",
        "programming",
        "debug",
        "function",
        "script",
        "run python",
        "write code",
        "fix code",
        "coding"
    ]

    if any(
        keyword in task
        for keyword in code_keywords
    ):

        return "code"

    # =====================================================
    # TEXT
    # =====================================================

    return "text"


# =========================================================
# GET ACTUAL OLLAMA MODEL
# =========================================================

def get_model_for_task(
    task_type: str
) -> str:
    """
    Return the local Ollama model corresponding
    to the selected task type.
    """

    task_type = (
        task_type or ""
    ).lower().strip()

    if task_type == "vision":

        return DEFAULT_VISION_MODEL

    if task_type == "code":

        return get_installed_code_model()

    return DEFAULT_TEXT_MODEL