"""Receive an independently pinned Freight ZIP entirely in memory; never extract or execute it."""
import base64
import hashlib
import io
import json
import struct
import zipfile

def _require(ok, label):
    if not ok:
        raise ValueError(label)

def _pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(body)).encode() + b"\0" + body).hexdigest()}

def receive_zip(base64_text, contract, package_receipt):
    """base64_text is the exact unwrapped framed payload, not arbitrary log text."""
    _require(isinstance(base64_text, str), "base64 must be text")
    _require(len(base64_text) <= 1400000, "bounded encoded ZIP")
    _require(not any(c.isspace() for c in base64_text), "unwrap only verified framing")
    raw = base64.b64decode(base64_text, validate=True)
    _require(base64.b64encode(raw).decode() == base64_text, "canonical base64")
    _require(22 <= len(raw) <= 1048576, "bounded ZIP")
    expected = contract["members"]
    names = sorted(expected)
    _require(len(names) == 11 and "site/scenario-record.mjs" in names, "eleven-member contract")
    # Reject prefixes, appended bytes/comments, multidisk/ZIP64 and hidden local records.
    end = struct.unpack("<4s4H2IH", raw[-22:])
    sig, disk, central_disk, count_disk, count, central_size, central_at, comment_size = end
    _require(sig == b"PK\x05\x06" and disk == central_disk == comment_size == 0,
             "single disk, final uncommented EOCD")
    _require(count_disk == count == len(names), "EOCD entry count")
    _require(central_at + central_size == len(raw) - 22, "exact central-directory extent")
    actual = {}
    payloads = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        _require([i.filename for i in infos] == names, "exact unique sorted paths")
        _require(not archive.comment and archive.start_dir == central_at, "archive boundary")
        next_local = 0
        for info in infos:
            name = info.filename
            encoded_name = name.encode("ascii")
            _require(info.orig_filename == name and not info.is_dir(), "literal regular member")
            _require(info.header_offset == next_local, "contiguous local records without prefix")
            _require(info.create_system == 3 and info.external_attr == (0o100644 << 16),
                     "Unix regular-file mode 0644")
            _require(info.internal_attr == 0 and info.flag_bits == 0,
                     "no encryption, descriptors or extra flags")
            _require(info.compress_type == zipfile.ZIP_DEFLATED, "DEFLATE")
            _require(info.date_time == (1980, 1, 1, 0, 0, 0), "deterministic timestamp")
            _require(not info.extra and not info.comment, "no entry extras/comments")
            _require(info.file_size == expected[name]["bytes"], "bounded member size: " + name)
            local = struct.unpack_from("<4s5H3I2H", raw, next_local)
            lsig, version, flags, method, time, date, crc, compressed, size, nl, el = local
            _require(lsig == b"PK\x03\x04" and flags == 0 and method == 8
                     and time == 0 and date == 33 and el == 0, "local metadata: " + name)
            _require(version == info.extract_version and crc == info.CRC
                     and compressed == info.compress_size and size == info.file_size,
                     "local/central sizes and CRC: " + name)
            _require(nl == len(encoded_name)
                     and raw[next_local + 30:next_local + 30 + nl] == encoded_name,
                     "local/central name: " + name)
            next_local += 30 + nl + compressed
            _require(next_local <= central_at, "member exceeds local-data extent")
            body = archive.read(info)  # zipfile verifies CRC while fully decompressing.
            actual[name] = _pin(body)
            _require(actual[name] == expected[name], "member bytes/SHA/Git: " + name)
            payloads[name] = body
        _require(next_local == central_at, "no hidden local members/data")
        cursor = central_at
        for info in infos:
            fields = struct.unpack_from("<4s6H3I5H2I", raw, cursor)
            (sig, made, needed, flags, method, time, date, crc, compressed, size,
             nl, el, cl, diskstart, internal, external, local_at) = fields
            n = info.filename.encode("ascii")
            _require(sig == b"PK\x01\x02" and nl == len(n) and el == cl == diskstart == 0,
                     "canonical central record")
            _require(raw[cursor+46:cursor+46+nl] == n, "central name")
            _require(made == (info.create_system << 8) + info.create_version
                     and needed == info.extract_version and flags == 0 and method == 8
                     and time == 0 and date == 33 and crc == info.CRC
                     and compressed == info.compress_size and size == info.file_size
                     and internal == 0 and external == (0o100644 << 16)
                     and local_at == info.header_offset, "central metadata")
            cursor += 46 + nl
        _require(cursor == len(raw) - 22, "no unaccounted central bytes")
    _require(payloads["README.txt"].decode("utf-8") == contract["generated_readme"],
             "exact current resume instructions")
    _require(payloads["manifest.json"].decode("utf-8") == contract["expected_manifest_text"],
             "exact generated manifest and canonical provenance")
    manifest = json.loads(payloads["manifest.json"])
    _require(manifest == contract["manifest"], "semantic manifest")
    expected_receipt = {
        "schema": "workflow-checks.freight-whatif.bundle-receipt.v1",
        "archive_name": "freight-whatif.zip", "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(), "entries": names,
        "all_archive_entries_read_back_exact": True,
        "manifest_sha256": expected["manifest.json"]["sha256"],
        "packager_sha256": contract["packager"]["sha256"],
    }
    _require(package_receipt == expected_receipt, "actual packager receipt")
    return {"schema": "hamon.freight-zip-independent-receiving.v1",
            "status": "archive-content-accepted",
            "archive": _pin(raw), "members": actual,
            "source_contract_commit": contract["source_commit"],
            "source_contract_tree": contract["source_tree"],
            "scope": "In-memory complete archive readback. Hosted checkout/run/source-before-after "
                     "binding is a separate required gate; no product/browser/install acceptance."}
