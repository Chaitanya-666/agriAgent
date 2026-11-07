"""
src/vision/model_cache.py
Load each real model once per process, one load at a time.

F26 (manual test, 30 Oct): the app failed with "Cannot copy out of meta tensor; no data!" while
loading Grounding DINO. Every app run built a new VisionWorkflowRunner, so every run loaded the
weights again, and Streamlit can start a new run while the old one is still loading. Two loads at
once share transformers' loading state (weights are first created on the "meta" device and filled
in afterwards), and one of them ends up copying from an empty meta tensor.

The fix: keep loaded models in a process-wide cache and guard loading with a lock, so only one
load runs at a time and later runs reuse the loaded weights (also saves several seconds per run).
A load that still fails with the meta-tensor error is retried once, which worked by hand.
"""

import logging
import threading
from typing import Any, Callable, Dict, Hashable

logger = logging.getLogger("agriagent.vision.model_cache")

_LOCK = threading.Lock()
_CACHE: Dict[Hashable, Any] = {}


def load_once(key: Hashable, loader: Callable[[], Any], retries: int = 1) -> Any:
    """Return the cached value for key, calling loader() under the lock the first time."""
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]
        for attempt in range(retries + 1):
            try:
                value = loader()
                break
            except Exception as err:
                if attempt < retries and "meta tensor" in str(err).lower():
                    logger.warning("Model load hit the meta-tensor error (%s); retrying once.", err)
                    continue
                raise
        _CACHE[key] = value
        return value


def clear() -> None:
    """Forget every cached model (tests)."""
    with _LOCK:
        _CACHE.clear()
