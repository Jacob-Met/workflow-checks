"""Deterministic packet filename components for portable local output."""
from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Iterable

_PLAIN_STEM = re.compile(r"[A-Za-z0-9_-]{1,250}")
_DEVICE_STEMS = {"CON", "PRN", "AUX", "NUL"} | {
    prefix + str(number) for prefix in ("COM", "LPT") for number in range(1, 10)
}


def _plain_stem(load_id: str) -> bool:
    return _PLAIN_STEM.fullmatch(load_id) is not None and load_id.upper() not in _DEVICE_STEMS


def packet_filenames(load_ids: Iterable[str]) -> dict[str, str]:
    """Allocate one distinct basename for each load that will receive a packet.

    Ordinary ASCII stems keep their existing names when case-insensitively unique.
    The reserved '~' prefix separates mapped names from every ordinary stem.
    This handles filename components; the caller still owns its output directory.
    """
    ids = list(load_ids)
    if len(ids) != len(set(ids)):
        raise ValueError("packet load IDs must be unique")
    plain = {load_id for load_id in ids if _plain_stem(load_id)}
    counts = Counter(load_id.casefold() for load_id in plain)
    names = {}
    used = set()
    for load_id in ids:
        if load_id in plain and counts[load_id.casefold()] == 1:
            name = load_id + ".html"
        else:
            name = "~" + hashlib.sha256(load_id.encode("utf-8")).hexdigest() + ".html"
        folded = name.casefold()
        if folded in used:
            raise ValueError("packet filenames must be distinct")
        used.add(folded)
        names[load_id] = name
    return names
