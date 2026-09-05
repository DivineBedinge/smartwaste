"""Pre-verification IA non destructive et sans telechargement."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEIGHT_SUFFIXES = {".onnx", ".safetensors", ".bin", ".pt", ".pth"}


def _module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _weight_present(path: Path) -> bool:
    if path.is_file():
        return path.suffix.lower() in WEIGHT_SUFFIXES and path.stat().st_size > 0
    if path.is_dir():
        return any(p.suffix.lower() in WEIGHT_SUFFIXES and p.stat().st_size > 0 for p in path.rglob("*"))
    return False


def collect_status(*, verify_classifier: bool = False, verify_embeddings: bool = False, check_database: bool = False) -> dict:
    configured = {
        "severity": Path(os.getenv("MODEL_SEVERITY_PATH", ROOT / "smartwaste_mobilenetv2_clean.onnx")),
        "waste_type": Path(os.getenv("MODEL_TYPE_PATH", ROOT / "modele_12classes.onnx")),
        "binary": Path(os.getenv("MODEL_BINARY_PATH", ROOT / "modele_2classes.onnx")),
        "embeddings": ROOT / "models" / "multilingual-e5-small",
        "reranker": ROOT / "models" / "ms-marco-MiniLM-L-6-v2",
    }
    weights = {name: _weight_present(path) for name, path in configured.items()}
    dependencies = {
        "onnxruntime": _module("onnxruntime"),
        "sentence_transformers": _module("sentence_transformers"),
        "psycopg2": _module("psycopg2"),
    }
    disabled = os.getenv("SMARTWASTE_DISABLE_AI", "").lower() in {"1", "true", "yes"}
    classifier_ready = all(weights[name] for name in ("severity", "waste_type", "binary")) and dependencies["onnxruntime"]
    retrieval_ready = weights["embeddings"] and dependencies["sentence_transformers"]
    generator_configured = bool(os.getenv("OLLAMA_BASE_URL"))
    load_results: dict[str, str] = {"classifier": "not_checked", "embeddings": "not_checked"}
    if verify_classifier and classifier_ready:
        try:
            import onnxruntime as ort
            for name in ("severity", "waste_type", "binary"):
                ort.InferenceSession(str(configured[name]), providers=["CPUExecutionProvider"])
            load_results["classifier"] = "loaded"
        except Exception as error:
            load_results["classifier"] = f"failed:{type(error).__name__}"
            classifier_ready = False
    if verify_embeddings and retrieval_ready:
        try:
            from sentence_transformers import SentenceTransformer
            SentenceTransformer(str(configured["embeddings"]), local_files_only=True)
            load_results["embeddings"] = "loaded"
        except Exception as error:
            load_results["embeddings"] = f"failed:{type(error).__name__}"
            retrieval_ready = False
    pgvector: bool | str = "not_checked_without_database"
    documents: int | str = "not_checked_without_database"
    if check_database:
        try:
            import psycopg2
            with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")
                    pgvector = bool(cur.fetchone()[0])
                    cur.execute("SELECT COUNT(*) FROM chatbot_embeddings")
                    documents = int(cur.fetchone()[0])
        except Exception as error:
            pgvector = f"failed:{type(error).__name__}"
            documents = "unavailable"
    if disabled:
        mode = "degraded"
    elif classifier_ready and retrieval_ready and generator_configured:
        mode = "enabled"
    elif classifier_ready or retrieval_ready:
        mode = "partial"
    else:
        mode = "degraded"
    return {
        "mode": mode,
        "disabled_by_configuration": disabled,
        "dependencies": dependencies,
        "weights": weights,
        "components": {
            "classifier_loadable_prerequisites": classifier_ready,
            "retrieval_loadable_prerequisites": retrieval_ready,
            "load_verification": load_results,
            "generator_configured": generator_configured,
            "pgvector": pgvector,
            "documents_indexed": documents,
        },
        "minimum_resources": "CPU x86_64, 4 GiB RAM recommandes; a mesurer avec les poids reels",
        "notes": ["Aucun modele n'a ete telecharge", "Les chemins physiques ne sont pas exposes"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", choices=("json",), default="json")
    parser.add_argument("--verify-classifier", action="store_true")
    parser.add_argument("--verify-embeddings", action="store_true")
    parser.add_argument("--database", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(collect_status(verify_classifier=args.verify_classifier, verify_embeddings=args.verify_embeddings, check_database=args.database), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
