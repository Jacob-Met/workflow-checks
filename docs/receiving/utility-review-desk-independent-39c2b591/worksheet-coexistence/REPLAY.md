# Replay the bounded interoperability receipt

## Inspect the exact recorded evidence

Place these nine publication files in one directory, then run:

```sh
python3 unpack-receiving.py /absolute/new/received-utility-interop
```

The unpacker verifies the base64, gzip and raw-container SHA256/lengths, then every preserved file. It refuses an existing destination. The decoded directory contains both exact selected runtime trees, the independently authored fixture, the original/current report and worksheet files, all real HTTP/CLI outputs, the complete result, the original scripts and input source manifests.

The native full selected-source/artifact bundle and final custody pins are retained in `/Users/me/hamon-utility-interop-39c2b591-nw60sufe/FINAL_HANDOFF.json`. The public full-repository reference is `7a9ac0a8d3ea93bbe7ebc25c6f226924d2357ee8` / `4a50b0dff8488c14385d38187e6a45ccddd952a2`; local source snapshots have distinct explicitly closed ancestry.

## Run a new independent replay

The exact executed receiver is `receive_interop_v1.py`, SHA256 `886887e95fc37d1c36917b2f2d8c618943b082d6964248e1ed503983f4b9d0b8`. On the original native directory it can be run with a new `--out` path:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 receive_interop_v1.py --source candidate --out evidence/interop-new
```

For another directory or machine, preserve the decoded archive intact. Create a separate new replay directory containing copies of only `baseline/`, `candidate/`, `build_fixture_v1.py` and `receive_interop_v1.py`; create its empty `evidence/` and `temp/` directories. Run `PYTHONDONTWRITEBYTECODE=1 python3 build_fixture_v1.py`, then the receiver command above. This creates fresh synthetic source and a genuine current-loader history fixture. New UUID row IDs, absolute paths and artifact hashes are expected; the same account/field oracle must pass. No third-party package, live data, network API or browser is needed. Two temporary loopback listeners are started and stopped by the receiver.

Do not copy the recorded fixture oracle into a relocated replay as though its original absolute paths applied there. Its exact frozen bytes remain in the decoded archive; the fixture builder produces the correct fresh path bindings. The original prepared fixture and actual candidate run are distinct artifacts, not interchangeable results.
