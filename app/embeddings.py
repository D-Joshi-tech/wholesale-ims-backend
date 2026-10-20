# Embedding utility - wraps fastembed so it plays nicely with async FastAPI.
#
# Model: BAAI/bge-small-en-v1.5
#   - 384 dimensions
#   - Lazy-loaded to ensure serverless/Vercel boots instantly without crashing

import os
import asyncio
from typing import Any

EMBEDDING_DIM = 384
_MODEL_NAME = "BAAI/bge-small-en-v1.5"

_model: Any | None = None


def _get_model():
    """Lazy-load the model once; gracefully returns None if fastembed isn't present."""
    global _model
    if _model is None:
        try:
            from fastembed import TextEmbedding
            cache_dir = os.getenv("FASTEMBED_CACHE_DIR", "/tmp/cache/fastembed" if os.environ.get("VERCEL") else None)
            if cache_dir and not os.path.exists(cache_dir):
                try:
                    os.makedirs(cache_dir, exist_ok=True)
                except Exception:
                    pass
            _model = TextEmbedding(_MODEL_NAME, cache_dir=cache_dir)
        except Exception as e:
            print(f"Note: fastembed model not available in this environment ({e}); falling back to standard search.")
            return None
    return _model


def preload_model() -> None:
    """Call this at startup to load model. Safe in serverless."""
    if not os.environ.get("VERCEL"):
        try:
            _get_model()
        except Exception:
            pass


def _embed_sync(text: str) -> list[float] | None:
    model = _get_model()
    if model is None:
        return None
    try:
        result = list(model.embed([text]))
        return result[0].tolist()
    except Exception as e:
        print(f"Embedding generation error: {e}")
        return None


async def embed_text(text: str) -> list[float] | None:
    """
    Generate a 384-dim embedding vector asynchronously.
    Returns None if embedding model is not present.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _embed_sync, text)


def product_text(name: str, category: str | None, unit: str) -> str:
    """Build a single string to embed for a product."""
    parts = [name]
    if category:
        parts.append(category)
    parts.append(unit)
    return " ".join(parts)