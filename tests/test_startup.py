import os
import subprocess
import sys


def test_main_import_does_not_load_ai_models():
    env = {**os.environ, "SMARTWASTE_DISABLE_AI": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    code = (
        "import main; from app.services.ai_runtime import get_onnx_session, get_embedding_model, get_cross_encoder; "
        "assert get_onnx_session.cache_info().currsize == 0; "
        "assert get_embedding_model.cache_info().currsize == 0; "
        "assert get_cross_encoder.cache_info().currsize == 0"
    )
    subprocess.run([sys.executable, "-c", code], env=env, check=True, timeout=15)
