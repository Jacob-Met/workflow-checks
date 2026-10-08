# PT CSV header admission qualification

Canonical baseline: `8fe2c9270f487729af9e88f40894e1c4530f2c20`, tree
`ff97dbcf5ea9efe19e98d885c4694322a6fe627f`. The native capture
`177f440894067ed7af69b6a5467302f4235898de` contains exactly 30 PT runtime,
test, sample and documentation leaves (331,957 bytes), each verified against
its canonical Git blob. It is an executable closure capture, not complete
canonical history. Source publication applies only the qualified delta to the
fresh canonical tree and preserves other bodies there.

The only existing production edit is an eleven-line insertion immediately after
`csv.DictReader` creation in `ptauth/data.py::_rows`. Removing that insertion
recovers the original file bytes, including CRLF endings. The original
normalization, decoding, row mapping, domain/rule code and report publication
remain unchanged. Accepted header normalization is documented in
`pt_auth/CSV_HEADERS.md`.

Native ThinkPad qualification used Python 3.14.4 and installed pytest 9.0.2.
No dependency installation, borrowed cache mutation, service activation, real
patient data or payer call occurred.

- Original four actual CLI beforeimages all exited 0 on ambiguous schedule,
  authorization, payer and patient columns. Every case replaced its previous
  digest, summary and audit and wrote four new exports. Input files remained
  unchanged. The exact raw fixtures, generated reports, stdout/stderr and receipt
  are retained in baseline-witness.zip with member hashes.
- Original inherited PT suite: 125 passed, 45 subtests passed, one optional
  clinic-zone browser check skipped.
- The ten new maintained test methods were frozen with the contract at native
  commit `5374b335184117344b420c66d00cf685c4244291` before source editing.
  On unchanged production source they produced 20 failed assertions/subtests,
  confined to duplicate-header refusals and report preservation. Encoding,
  blank-column, multiline row/source-line and empty-file controls passed.
- Candidate complete captured PT suite: 135 passed, 63 subtests passed,
  zero failures; the same one optional browser check skipped because
  `PTAUTH_TEST_CHROME` was not configured. This is not a browser/layout claim.
  Existing report and HTTP tests in that suite ran normally.
- All 29 other original captured files retain their canonical blob hashes.

The exact production SHA256 changed from
`eeab8ab5b2b72524148969de0d13b27126cc64c4ec79b68a147b51b25a3741e2`
to
`b16d31711e678e3d25c9cf867098de93645298410985b96248e03ac3133adf19`.
The maintained test SHA256 is
`886acf93c97ef0b276d5c38ea49c9208d95731034a844aeb629d46a754a343e0`.

Source fence: workflow-checks issue58, native Conscience4858
`cev_4b32ed4ce58046d2a358334f`. Allocation inspection #43/#56, staff review
#38, Freight headers #51/#57 and Utility headers #24 retain their owners.
Independent root receiving and final source integration are separate gates and
are added only after the corresponding exact evidence is available.


## Independent source acceptance

Root's frozen receiver10446cf7 was executed before and after the correction:
original source3 passes/6 failures; exact candidate9/9. Each run used eight
real CLI processes. Six ambiguous inputs now refuse through the existing
exit2 path, preserving all seven prior report/audit files and the exact inputs.
The four input families, header-only and quoted multiline headers are covered.
BOM, cp1252, blank columns/rows, multiline values, physical row positions and
empty-file controls remain passing.

The receiver, reviewed source diff, both full receipts and formal ACCEPT are
retained verbatim under independent/. Candidate receipt SHA256:
8035bfdd262628ee2426b448f7298bb31b73d2ff8dc038233d125f870f955b80.
The independent review admits the exact11-line insertion and confirms the
other11 runtime leaves and report pipeline remain unchanged. No tests were
rerun when copying the evidence. Native Linux CLI/loader receiving does not
claim clinical validation, a browser run or installed runtime activation.
