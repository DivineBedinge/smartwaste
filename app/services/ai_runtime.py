import os
from functools import lru_cache


def heavy_ai_disabled() -> bool:
    return os.getenv("SMARTWASTE_DISABLE_AI", "").strip().lower() in {"1", "true", "yes"}


@lru_cache(maxsize=None)
def get_onnx_session(model_path: str):
    if heavy_ai_disabled():
        raise RuntimeError("Service IA désactivé")
    import onnxruntime as ort
    return ort.InferenceSession(model_path)


@lru_cache(maxsize=1)
def get_embedding_model():
    if heavy_ai_disabled():
        raise RuntimeError("Service IA désactivé")
    from sentence_transformers import SentenceTransformer
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    multilingual = os.path.join(root, "models", "multilingual-e5-small")
    mini = os.path.join(root, "models", "all-MiniLM-L6-v2")
    return SentenceTransformer(multilingual if os.path.exists(multilingual) else mini if os.path.exists(mini) else "all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def get_cross_encoder():
    if heavy_ai_disabled():
        return None
    try:
        from sentence_transformers import CrossEncoder
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        return CrossEncoder(os.path.join(root, "models", "ms-marco-MiniLM-L-6-v2"))
    except Exception:
        return None


def runtime_status() -> dict:
    disabled = heavy_ai_disabled()
    return {
        "classification": "degraded" if disabled else "available_on_demand",
        "chatbot": "degraded" if disabled else "available_on_demand",
    }
