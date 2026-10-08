"""The HTML must preserve the review decisions, identities and evidence from the engine."""
import copy
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uwatch.engine import run  # noqa: E402
from uwatch.report import write_html  # noqa: E402
from uwatch.synth import generate  # noqa: E402


@dataclass
class Element:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    @property
    def text(self):
        return "".join(child.text if isinstance(child, Element) else child for child in self.children).strip()

    def find(self, tag=None, **attrs):
        result = []
        for child in self.children:
            if not isinstance(child, Element):
                continue
            if (tag is None or child.tag == tag) and all(child.attrs.get(k) == v for k, v in attrs.items()):
                result.append(child)
            result.extend(child.find(tag, **attrs))
        return result


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        element = Element(tag, dict(attrs))
        self.stack[-1].children.append(element)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(element)

    def handle_endtag(self, tag):
        assert self.stack[-1].tag == tag, f"Malformed report: closing {tag} inside {self.stack[-1].tag}"
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1].children.append(data)


@pytest.fixture
def review(tmp_path):
    generate(tmp_path / "data", seed=11)
    summary = run(tmp_path / "data", tmp_path / "out")
    return summary, tmp_path / "out" / "report.html"


def _identity(record):
    fields = record.find("dl")[0]
    return {item.find("dt")[0].text: item.find("dd")[0].text
            for item in fields.children if isinstance(item, Element)}


def _evidence(record):
    return [item.text for item in record.find("ul", **{"class": "evidence"})[0].find("code")]


def _records(document, section):
    return document.find("section", id=section)[0].find("li", **{"class": "record"})


def test_report_preserves_every_decision_identity_and_source_row(review):
    summary, path = review
    doc = Document(path.read_text()).root
    actual_flags = []
    for prop in doc.find("details", **{"class": "property"}):
        name = prop.find("summary")[0].children[0]
        for record in prop.find("li", **{"class": "record"}):
            fields = _identity(record)
            actual_flags.append({
                "property": name, "utility": fields["Utility"], "account_no": fields["Account"],
                "key": fields["Bill / expected period"], "code": record.find("code")[0].text,
                "detail": record.find("p")[0].text, "evidence": _evidence(record),
            })
    assert actual_flags == sorted(summary["flags_detail"], key=lambda x: (x["property"], x["code"], x["key"]))

    actual_exceptions = []
    for record in _records(doc, "exceptions"):
        fields = _identity(record)
        actual_exceptions.append({
            "key": fields["Bill / expected period"], "account_no": fields["Account"],
            "reason": record.find("h3")[0].text, "detail": record.find("p")[0].text,
            "evidence": _evidence(record),
        })
    assert actual_exceptions == summary["exceptions_detail"]

    actual_queue = []
    for record in _records(doc, "payment-queue"):
        fields = _identity(record)
        actual_queue.append({
            "property": fields["Property"], "utility": fields["Utility"], "vendor": fields["Vendor"],
            "account_no": fields["Account"], "bill_id": fields["Bill"], "invoice": fields["Invoice"],
            "amount_due": float(record.find("strong")[0].text.replace("$", "").replace(",", "")),
            "due_date": record.find("h3")[0].text.removeprefix("Due "),
            "status": record.find("code", **{"class": "status"})[0].text,
            "evidence": _evidence(record)[0],
        })
    # List equality also guards the engine's due-date ordering and ordering of tied bills.
    assert actual_queue == summary["payment_queue_detail"]


def test_export_text_cannot_create_markup_or_links(review):
    summary, path = review
    hostile = '\"><img src=x onerror=alert(1)><script>alert(1)</script>&'
    for key in ("as_of", "eval_from"):
        summary[key] = hostile
    for item in summary["flags_detail"]:
        for key in ("property", "utility", "account_no", "key", "code", "detail"):
            item[key] = hostile
        item["evidence"] = [hostile]
    for item in summary["exceptions_detail"]:
        for key in ("key", "account_no", "reason", "detail"):
            item[key] = hostile
        item["evidence"] = [hostile]
    for item in summary["payment_queue_detail"]:
        for key in ("property", "utility", "vendor", "account_no", "bill_id", "invoice", "status", "evidence", "due_date"):
            item[key] = hostile
    summary["by_code"] = {hostile: summary["flags"]}
    write_html(path, summary, summary["payment_queue_detail"])
    doc = Document(path.read_text()).root
    assert not doc.find("script") and not doc.find("img")
    assert all(not key.lower().startswith("on") for node in doc.find() for key in node.attrs)
    assert all(link.attrs["href"].startswith("#") for link in doc.find("a"))
    for section in ("flags", "exceptions", "payment-queue"):
        assert all(hostile in record.text and _evidence(record) == [hostile] for record in _records(doc, section))


def test_empty_client_review_has_explicit_queues_and_working_destinations(review):
    summary, path = review
    summary.update(data_mode="client_csv", flags=0, exceptions=0, payment_queue=0,
                   payment_queue_total=0, by_code={}, flags_detail=[], exceptions_detail=[], payment_queue_detail=[])
    write_html(path, summary, [])
    doc = Document(path.read_text()).root
    assert "REVIEW ONLY." in doc.text and "SYNTHETIC" not in doc.text
    assert "No flags in this review window." in doc.text
    assert "No items in the exception queue." in doc.text
    assert "No clean, unpaid bills queued for approval." in doc.text
    assert not doc.find("details")
    ids = [node.attrs["id"] for node in doc.find() if "id" in node.attrs]
    assert len(ids) == len(set(ids))
    assert all(link.attrs["href"][1:] in ids for link in doc.find("a"))


def test_rendering_is_repeatable_and_does_not_change_review_data(review):
    summary, path = review
    original = copy.deepcopy(summary)
    first = path.read_bytes()
    write_html(path, summary, summary["payment_queue_detail"])
    assert path.read_bytes() == first
    assert summary == original
