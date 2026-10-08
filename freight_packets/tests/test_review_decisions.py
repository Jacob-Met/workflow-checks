import csv
import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer

import pytest

from freightpkt.pipeline import run
from freightpkt.synth import generate
from freightpkt.web import App, make_handler


@pytest.fixture
def review(tmp_path):
    data, out = tmp_path / "data", tmp_path / "out"
    generate(data, n_loads=24, seed=7)
    run(data, out)
    app = App(data, out)
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def request(path, body=None):
        req = urllib.request.Request(
            base + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                raw = response.read()
                return response.status, json.loads(raw) if response.headers.get_content_type() == "application/json" else raw
        except urllib.error.HTTPError as error:
            raw = error.read()
            return error.code, json.loads(raw) if error.headers.get_content_type() == "application/json" else raw

    yield app, request
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def approve(request, summary, load_id, note="checked the packet"):
    return request("/api/decision", {
        "load_id": load_id, "decision": "approve", "note": note,
        "evidence_version": summary.get("evidence_versions", {}).get(load_id),
    })


def edit_carrier(data, load_id, carrier):
    path = data / "loads.csv"
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        fields, rows = reader.fieldnames, list(reader)
    for row in rows:
        if row["load_id"] == load_id:
            row["carrier"] = carrier
    with path.open("w", newline="", encoding="utf-8") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_changed_packet_evidence_requires_review_and_preserves_note(review):
    app, request = review
    _, before = request("/api/summary")
    load_id = before["packets"][0]["load_id"]
    assert approve(request, before, load_id)[0] == 200
    edit_carrier(app.data_dir, load_id, "Changed synthetic carrier")
    status, after = request("/api/run", {})
    assert status == 200
    assert after["decisions"][load_id].get("review_state", "current") == "stale"
    assert after["decisions"][load_id]["note"] == "checked the packet"


def test_unchanged_rerun_and_other_load_changes_preserve_review(review):
    app, request = review
    _, before = request("/api/summary")
    reviewed, other = [p["load_id"] for p in before["packets"][:2]]
    assert approve(request, before, reviewed)[0] == 200
    assert approve(request, before, other)[0] == 200
    _, repeated = request("/api/run", {})
    assert repeated["evidence_versions"] == before["evidence_versions"]
    assert repeated["decisions"][reviewed]["review_state"] == "current"
    edit_carrier(app.data_dir, other, "A different synthetic carrier")
    _, changed = request("/api/run", {})
    assert changed["evidence_versions"][reviewed] == before["evidence_versions"][reviewed]
    assert changed["decisions"][reviewed]["review_state"] == "current"
    assert changed["decisions"][other]["review_state"] == "stale"


def test_stale_client_cannot_approve_recalculated_evidence(review):
    app, request = review
    _, before = request("/api/summary")
    load_id = before["packets"][0]["load_id"]
    assert approve(request, before, load_id, "original note")[0] == 200
    edit_carrier(app.data_dir, load_id, "Replacement carrier")
    _, after = request("/api/run", {})
    decision_bytes = app.decisions_path.read_bytes()
    audit_bytes = (app.out_dir / "audit.jsonl").read_bytes()
    status, error = approve(request, before, load_id, "stale browser note")
    assert status == 409 and "reload" in error["error"].lower()
    assert app.decisions_path.read_bytes() == decision_bytes
    assert (app.out_dir / "audit.jsonl").read_bytes() == audit_bytes
    status, decisions = approve(request, after, load_id, "reviewed replacement")
    assert status == 200
    assert decisions[load_id]["review_state"] == "current"
    prior = decisions[load_id]["history"][-1]
    assert prior["note"] == "original note"
    assert prior["evidence_version"] == before["evidence_versions"][load_id]


@pytest.mark.parametrize("override", [
    {"load_id": "not-a-current-load"},
    {"evidence_version": None},
    {"evidence_version": ""},
    {"decision": "unrecognized"},
])
def test_invalid_review_never_changes_saved_decisions_or_audit(review, override):
    app, request = review
    _, summary = request("/api/summary")
    load_id = summary["packets"][0]["load_id"]
    assert approve(request, summary, load_id)[0] == 200
    before = app.decisions_path.read_bytes()
    audit_before = (app.out_dir / "audit.jsonl").read_bytes()
    body = {"load_id": load_id, "decision": "approve",
            "evidence_version": summary["evidence_versions"][load_id], **override}
    assert request("/api/decision", body)[0] == 400
    assert app.decisions_path.read_bytes() == before
    assert (app.out_dir / "audit.jsonl").read_bytes() == audit_before


def test_removed_load_keeps_historical_decision_but_cannot_be_reviewed(review):
    app, request = review
    _, before = request("/api/summary")
    load_id = before["packets"][0]["load_id"]
    assert approve(request, before, load_id)[0] == 200
    # A new current run can omit a prior load. Old packet files must not make it current.
    summary_path = app.out_dir / "summary.json"
    summary = json.loads(summary_path.read_text())
    summary["packets"] = [p for p in summary["packets"] if p["load_id"] != load_id]
    summary_path.write_text(json.dumps(summary))
    _, after = request("/api/summary")
    assert after["decisions"][load_id]["review_state"] == "missing"
    assert after["decisions"][load_id]["note"] == "checked the packet"
    assert approve(request, before, load_id)[0] == 400


def test_legacy_review_requires_reverification_and_is_retained(review):
    app, request = review
    _, summary = request("/api/summary")
    load_id = summary["packets"][0]["load_id"]
    legacy = {"decision": "approve", "note": "legacy note", "at": "2026-01-01T00:00:00Z"}
    app.decisions_path.write_text(json.dumps({load_id: legacy}))
    _, after = request("/api/summary")
    assert after["decisions"][load_id]["review_state"] == "unbound"
    assert app.decisions_path.read_text() == json.dumps({load_id: legacy})
    status, updated = approve(request, after, load_id, "new review")
    assert status == 200
    assert updated[load_id]["history"][-1] == legacy


def test_packet_bytes_and_related_report_changes_invalidate_review(review):
    app, request = review
    _, before = request("/api/summary")
    load_id = before["packets"][0]["load_id"]
    assert approve(request, before, load_id)[0] == 200
    packet = app.out_dir / before["packets"][0]["file"]
    packet.write_text(packet.read_text() + "<p>Additional synthetic evidence</p>")
    _, after = request("/api/summary")
    assert after["decisions"][load_id]["review_state"] == "stale"
    assert after["evidence_versions"][load_id] != before["evidence_versions"][load_id]
    assert approve(request, after, load_id)[0] == 200
    summary_path = app.out_dir / "summary.json"
    report = json.loads(summary_path.read_text())
    report["exceptions"].append({"load_id": load_id, "stop": "", "reason": "new evidence exception", "evidence": "test.csv:row2"})
    summary_path.write_text(json.dumps(report))
    _, changed = request("/api/summary")
    assert changed["decisions"][load_id]["review_state"] == "stale"


def test_missing_packet_cannot_keep_or_receive_an_approval(review):
    app, request = review
    _, before = request("/api/summary")
    load_id = before["packets"][0]["load_id"]
    assert approve(request, before, load_id)[0] == 200
    (app.out_dir / before["packets"][0]["file"]).unlink()
    _, after = request("/api/summary")
    assert after["decisions"][load_id]["review_state"] == "missing"
    assert load_id not in after["evidence_versions"]
    assert approve(request, before, load_id)[0] == 400


def test_clear_and_regenerate_preserve_previous_decisions(review):
    app, request = review
    _, before = request("/api/summary")
    load_id = before["packets"][0]["load_id"]
    assert approve(request, before, load_id, "before clear")[0] == 200
    status, cleared = request("/api/decision", {
        "load_id": load_id, "decision": "clear",
        "evidence_version": before["evidence_versions"][load_id],
    })
    assert status == 200
    assert cleared[load_id]["review_state"] == "cleared"
    assert cleared[load_id]["history"][-1]["note"] == "before clear"
    assert approve(request, before, load_id, "before regeneration")[0] == 200
    status, regenerated = request("/api/generate", {"loads": 24, "seed": 11})
    assert status == 200
    assert regenerated["decisions"][load_id]["review_state"] in ("stale", "missing")
    assert regenerated["decisions"][load_id]["note"] == "before regeneration"


def test_versioned_packet_read_rejects_stale_view(review):
    app, request = review
    _, before = request("/api/summary")
    packet = before["packets"][0]
    load_id = packet["load_id"]
    old_url = "/out/" + packet["file"] + "?evidence_version=" + before["evidence_versions"][load_id]
    assert request(old_url)[0] == 200
    edit_carrier(app.data_dir, load_id, "Changed after summary")
    _, after = request("/api/run", {})
    assert request(old_url)[0] == 409
    new_url = "/out/" + packet["file"] + "?evidence_version=" + after["evidence_versions"][load_id]
    assert request(new_url)[0] == 200


def test_concurrent_reviews_of_distinct_loads_keep_both(review):
    app, request = review
    _, summary = request("/api/summary")
    ids = [p["load_id"] for p in summary["packets"][:4]]
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda lid: approve(request, summary, lid), ids))
    assert all(status == 200 for status, _ in results)
    _, final = request("/api/summary")
    assert all(final["decisions"][lid]["review_state"] == "current" for lid in ids)
    records = [json.loads(row) for row in (app.out_dir / "audit.jsonl").read_text().splitlines()]
    reviews = [row for row in records if row["action"] == "reviewer_decision"]
    assert {row["load_id"] for row in reviews} == set(ids)
    assert all(row["evidence_version"] == summary["evidence_versions"][row["load_id"]] for row in reviews)


def test_failed_decision_replace_preserves_prior_saved_record(review, monkeypatch):
    import freightpkt.web as web
    app, request = review
    _, summary = request("/api/summary")
    load_id = summary["packets"][0]["load_id"]
    assert approve(request, summary, load_id)[0] == 200
    old_bytes = app.decisions_path.read_bytes()
    old_audit = (app.out_dir / "audit.jsonl").read_bytes()

    def fail_replace(*args):
        raise OSError("simulated storage failure")

    monkeypatch.setattr(web.os, "replace", fail_replace)
    status, _ = request("/api/decision", {
        "load_id": load_id, "decision": "reject",
        "evidence_version": summary["evidence_versions"][load_id],
    })
    assert status == 500
    assert app.decisions_path.read_bytes() == old_bytes
    assert (app.out_dir / "audit.jsonl").read_bytes() == old_audit
    assert not list(app.out_dir.glob(".decisions-*.tmp"))


def test_failed_pipeline_run_does_not_rebind_saved_approval(review, monkeypatch):
    import freightpkt.web as web
    app, request = review
    _, summary = request("/api/summary")
    load_id = summary["packets"][0]["load_id"]
    assert approve(request, summary, load_id)[0] == 200
    old_bytes = app.decisions_path.read_bytes()

    def fail_run(*args, **kwargs):
        raise ValueError("input cannot be parsed")

    monkeypatch.setattr(web, "run", fail_run)
    assert request("/api/run", {})[0] == 400
    assert app.decisions_path.read_bytes() == old_bytes
    _, after = request("/api/summary")
    assert after["decisions"][load_id]["review_state"] == "current"
    assert after["evidence_versions"][load_id] == summary["evidence_versions"][load_id]


def test_run_metadata_does_not_change_the_reviewed_evidence(review):
    app, request = review
    _, before = request("/api/summary")
    load_id = before["packets"][0]["load_id"]
    assert approve(request, before, load_id)[0] == 200
    summary_path = app.out_dir / "summary.json"
    raw = json.loads(summary_path.read_text())
    raw["generated_at"] = "2099-01-01T00:00:00"
    summary_path.write_text(json.dumps(raw))
    _, after = request("/api/summary")
    assert after["evidence_versions"] == before["evidence_versions"]
    assert after["decisions"][load_id]["review_state"] == "current"
