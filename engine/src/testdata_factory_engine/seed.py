from __future__ import annotations

import hashlib
import random


def stable_seed(*parts: object) -> int:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"\x00")
    return int.from_bytes(digest.digest()[:8], "big")


def seeded_random(*parts: object) -> random.Random:
    return random.Random(stable_seed(*parts))
