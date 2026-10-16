# Independent Freight supervisor lifecycle receiving

This packet qualifies the lifecycle helpers in `receive_browser_hosted-reviewed-v5.py`, SHA-256 `b9735d6efbfcbe62ca9d26d945be2798f91ed1addd08a34f948862fa9d291649`. It does not execute main(), Chrome, Puppeteer, npm, the Freight app or a network request.

The original contract was frozen before supervisor implementation inspection and receiver authoring. A separate diagnostic-failure addendum was frozen after the source review found a concrete cleanup hazard, before receiver execution. All seven controls ran once against the same final source; no oracle was changed after a candidate result.

The first run passed seven controls with explicit process exit 0 and empty stderr. The longest control took 5.85 seconds; total child time was 11.75 seconds. Raw streams and process status are under `execution-v1/`; the full per-control identities, events, signal attempts and own cleanup are in `run-v1/receipt.json`.

- A registered separate group was closed after its mock Node parent exited.
- A separate different-profile sentinel stayed alive with the same identity and received no signal attempt.
- Wrong start identity, registration-profile mismatch and live-process profile mismatch each refused without a signal call.
- A previously verified, naturally exited and reaped group succeeded without signaling.
- A disclosed syscall adapter released a pipe-waiting mock after the last verification, reaped it, then invoked the original killpg; the kernel's actual ESRCH was accepted only after empty-group observation.
- A TERM-ignoring own mock received TERM followed by bounded KILL.
- An event sink raising OSError produced diagnostic_error records while cleanup still closed the owned group.

Every fixture process was created by this receiver, had a unique profile marker, and was registered by PID/start ticks/UID/PGID/SID. An independent signal guard rechecked every group member and rejected any target outside the control's allowed registry before a real signal. Each mock had a 22-second self-expiry; controls had a 25-second deadline and bounded own cleanup. The receiver made itself a subreaper only within its own process so it could reap the mock parent's orphaned child. It did not inspect or clean another worker's browser group.

The supervisor source was copied byte-for-byte from the accepted author source and remained unchanged. `mock_process.py`, `receive_lifecycle_v1.py`, both contracts and the exact source are pinned in `pre-execution-manifest.json`. The qualification launcher `run-frozen-v1.py` records the original native absolute path; it is evidence of this run. For a separately authorized repeat, the receiver itself resolves its inputs beside its own file and refuses an existing `run-v1` output directory.

This packet is infrastructure qualification only. The earlier real browser timeout, Node exit −9, absent completed group output and unclassified hang retain their separate evidence. No claim is made that these mocks reproduce that hang or establish product/browser acceptance.
