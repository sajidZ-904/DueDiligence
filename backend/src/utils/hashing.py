from __future__ import annotations

import hashlib
import json
from typing import Any


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def sha256_json(value: Any) -> str:
    data = json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return sha256_text(data)

