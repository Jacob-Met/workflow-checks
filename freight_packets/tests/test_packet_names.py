"""Packet identity and filename retention across case-insensitive filesystems."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from html import escape
from pathlib import Path

from freightpkt.pipeline import run
from freightpkt.synth import generate
from freightpkt.web import App


class PacketNameAllocationTests(unittest.TestCase):
    def setUp(self):
        from freightpkt.packet_names import packet_filenames
        self.allocate = packet_filenames

    def test_ordinary_names_and_component_boundary_are_preserved(self):
        ids = ["LD260900", "abc-123", "under_score", "-leading", "X" * 250]
        self.assertEqual(self.allocate(ids), {lid: lid + ".html" for lid in ids})

    def test_case_collisions_are_distinct_and_order_independent(self):
        ids = ["LD260900", "ld260900", "Ld260900", "other"]
        names = self.allocate(iter(ids))
        self.assertEqual(names, self.allocate(reversed(ids)))
        self.assertEqual(len({name.casefold() for name in names.values()}), len(ids))
        self.assertEqual(names["other"], "other.html")
        for lid in ids[:3]:
            self.assertRegex(names[lid], r"^~[0-9a-f]{64}\.html$")

    def test_windows_device_names_are_not_used_as_stems(self):
        ids = ["CON", "prn", "Aux", "NUL", "COM1", "com9", "LPT1", "lpt9", "COM\u00b2", "NUL.txt"]
        names = self.allocate(ids)
        self.assertEqual(len(set(names.values())), len(ids))
        for lid in ids:
            with self.subTest(load_id=lid):
                self.assertRegex(names[lid], r"^~[0-9a-f]{64}\.html$")
        self.assertEqual(self.allocate(["COM0", "LPT10"]), {"COM0": "COM0.html", "LPT10": "LPT10.html"})

    def test_mapped_namespace_cannot_be_used_by_a_plain_load_id(self):
        mapped_stem = "~" + hashlib.sha256(b"NUL").hexdigest()
        names = self.allocate(["NUL", mapped_stem])
        self.assertNotEqual(names["NUL"], names[mapped_stem])
        self.assertEqual(names["NUL"], mapped_stem + ".html")

    def test_other_components_are_bounded_ascii_basenames(self):
        ids = ["", ".", "..", "../outside", "a/b", "a\\b", "a:b", "trailing.", "trailing ",
               "control\0byte", "\u212a", "X" * 251]
        names = self.allocate(ids)
        self.assertEqual(len(set(names.values())), len(ids))
        for lid, name in names.items():
            with self.subTest(load_id=lid):
                self.assertRegex(name, r"^~[0-9a-f]{64}\.html$")
                self.assertEqual(Path(name).name, name)
                self.assertLessEqual(len(name), 255)

    def test_repeated_identity_is_refused_before_allocation(self):
        with self.assertRaisesRegex(ValueError, "load IDs must be unique"):
            self.allocate(["same", "same"])
        self.assertEqual(self.allocate([]), {})


class PacketFileRetentionTests(unittest.TestCase):
    """These four controls also run unchanged against the original pipeline."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.out = self.root / "out"
        self.expected = generate(self.data, 8, 7)

    def replace_id(self, old, new):
        with (self.data / "loads.csv").open(encoding="utf-8", newline="") as source:
            self.assertEqual(sum(row["load_id"] == old for row in csv.DictReader(source)), 1,
                             "replacement must target one actual fixture load")
        replacements = 0
        for path in self.data.rglob("*"):
            if path.is_file():
                raw = path.read_bytes()
                if old.encode() in raw:
                    replacements += raw.count(old.encode())
                    path.write_bytes(raw.replace(old.encode(), new.encode()))
        self.assertGreater(replacements, 0, "fixture replacement must occur")

    def run_and_check(self):
        before = {p.relative_to(self.data).as_posix(): p.read_bytes()
                  for p in self.data.rglob("*") if p.is_file()}
        result = run(self.data, self.out)
        packets = result["packets"]
        self.assertEqual(result["detention_total_cents"], self.expected["detention_total_cents"])
        self.assertEqual(len(packets), 7)
        self.assertEqual(len({p["file"].casefold() for p in packets}), 7)
        self.assertEqual(len(list((self.out / "packets").glob("*.html"))), 7)
        app = App(self.data, self.out)
        view = app.summary()
        for packet in packets:
            with self.subTest(load_id=packet["load_id"]):
                path = self.out / packet["file"]
                self.assertEqual(path.parent, self.out / "packets")
                self.assertTrue(path.is_file())
                self.assertNotRegex(path.stem.upper(), r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$")
                expected_title = "<title>Detention packet " + escape(packet["load_id"]) + "</title>"
                self.assertIn(expected_title, path.read_text(encoding="utf-8"))
                _, content = app.output(packet["file"], view["evidence_versions"][packet["load_id"]])
                self.assertEqual(content, path.read_bytes())
        drafted = [json.loads(line) for line in (self.out / "audit.jsonl").read_text().splitlines()
                   if json.loads(line)["action"] == "packet_drafted"]
        self.assertEqual({row["load_id"]: row["file"] for row in drafted},
                         {row["load_id"]: Path(row["file"]).name for row in packets})
        self.assertEqual(before, {p.relative_to(self.data).as_posix(): p.read_bytes()
                                 for p in self.data.rglob("*") if p.is_file()})
        return result, app, view

    def test_ordinary_paths_keep_existing_layout(self):
        result, _, _ = self.run_and_check()
        self.assertTrue(all(p["file"] == "packets/" + p["load_id"] + ".html"
                            for p in result["packets"]))

    def test_case_distinct_loads_keep_distinct_readable_packets(self):
        self.replace_id("LD260907", "ld260900")
        result, _, _ = self.run_and_check()
        names = {p["load_id"]: p["file"] for p in result["packets"]}
        self.assertIn("LD260900", names)
        self.assertIn("ld260900", names)
        self.assertFalse((self.out / names["LD260900"]).samefile(self.out / names["ld260900"]))

    def test_device_load_id_has_a_retained_packet_and_existing_handoff(self):
        self.replace_id("LD260900", "NUL")
        result, app, view = self.run_and_check()
        packet = next(p for p in result["packets"] if p["load_id"] == "NUL")
        _, bundle = app.review_bundle("NUL", view["evidence_versions"]["NUL"],
                                      view["review_versions"]["NUL"])
        with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
            self.assertEqual(archive.read("packet.html"), (self.out / packet["file"]).read_bytes())

    def test_nonpacket_load_does_not_rename_an_existing_packet(self):
        self.replace_id("LD260942", "ld260900")
        result, _, _ = self.run_and_check()
        names = {p["load_id"]: p["file"] for p in result["packets"]}
        self.assertNotIn("ld260900", names)
        self.assertEqual(names["LD260900"], "packets/LD260900.html")


if __name__ == "__main__":
    unittest.main()
