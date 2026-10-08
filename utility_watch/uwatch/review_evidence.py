"""Read source records for one admitted current worksheet finding."""
from __future__ import annotations

import tempfile
from pathlib import Path

from . import evidence, review

MAX_EVIDENCE_BYTES = 8 * 1024 * 1024
FINDING_FIELDS = (
    "kind", "account_no", "finding_key", "code", "property", "utility",
    "detail", "finding_id", "evidence_version",
)
REPORT_FIELDS = ("as_of", "eval_from", "data_mode")


class EvidenceChanged(ValueError):
    """The configured source/report no longer describes the selected saved finding."""


def inspect_evidence(data: Path, report: Path, row: dict, metadata: dict) -> bytes:
    """Return the existing native producer's bytes after exact worksheet binding."""
    if row["row_state"] != "current":
        raise ValueError("Source inspection is available only for current saved findings.")
    # The established writer retains source admission, record parsing and final
    # custody rechecks. Its only output is private to this request and is removed.
    with tempfile.TemporaryDirectory(prefix="uwatch-desk-evidence-") as temporary:
        out = Path(temporary) / "evidence.json"
        document = evidence.write_evidence(
            data, report, out, kind=row["kind"], account=row["account_no"],
            key=row["finding_key"], code=row["code"],
        )
        finding = document["finding"]
        if (any(finding[key] != row[key] for key in FINDING_FIELDS) or
                finding["evidence"] != review._read_json(row["evidence"].encode("utf-8")) or
                any(document["review"][key] != row[key] or
                    document["review"][key] != metadata[key] for key in REPORT_FIELDS)):
            raise EvidenceChanged(
                "The source export and report do not match this saved finding. "
                "Keep your notes and reconcile a new worksheet with uwatch review --previous."
            )
        with out.open("rb") as source:
            raw = source.read(MAX_EVIDENCE_BYTES + 1)
        if len(raw) > MAX_EVIDENCE_BYTES:
            raise ValueError(
                "Source evidence exceeds the desk's 8 MiB limit. "
                "Inspect this finding with the uwatch evidence command."
            )
    return raw
