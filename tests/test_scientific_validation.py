from scripts.ai_preflight import collect_status
from scripts.evaluate_classifier import evaluate


def test_ai_preflight_never_claims_missing_weights(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MODEL_SEVERITY_PATH", str(tmp_path / "missing.onnx"))
    monkeypatch.setenv("MODEL_TYPE_PATH", str(tmp_path / "missing-type.onnx"))
    monkeypatch.setenv("MODEL_BINARY_PATH", str(tmp_path / "missing-binary.onnx"))
    status = collect_status(verify_classifier=False, verify_embeddings=False, check_database=False)
    assert status["mode"] in {"partial", "degraded"}
    assert status["components"]["classifier_loadable_prerequisites"] is False
    assert str(tmp_path) not in str(status)


def test_classifier_metrics_are_computed_without_sklearn():
    rows = [
        {"actual": "a", "predicted": "a", "confidence": "0.9", "latency_ms": "10"},
        {"actual": "a", "predicted": "b", "confidence": "0.7", "latency_ms": "20"},
        {"actual": "b", "predicted": "b", "confidence": "0.8", "latency_ms": "30"},
    ]
    result = evaluate(rows)
    assert result["samples"] == 3
    assert result["accuracy"] == 2 / 3
    assert result["human_review_rate_at_0_80"] == 1 / 3
    assert result["mean_inference_ms"] == 20
