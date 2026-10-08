# Packet filenames and load identities

Freight packets retain the supplied load ID in the HTML, reports and review identity.
Open or download a packet through the existing `packets[].file` value in
`summary.json`; do not reconstruct that path from its load ID.

Ordinary load IDs made only from ASCII letters, digits, underscores and hyphens
(up to 250 characters) keep `packets/<load_id>.html` when their name is unique
without regard to case among the loads receiving packets. Windows device names
such as `NUL`, `CON`, `COM1` and `LPT1` are excluded from this ordinary form.

When a load ID needs a mapped name, its filename is `~<sha256>.html`, where the
digest covers the exact UTF-8 load ID. This applies to device names, other
characters, longer components, and every member of a case-colliding group. The
reserved `~` prefix keeps mapped names separate from ordinary names. Allocation
is independent of load order, and all resulting names are checked for distinctness
before any packet is written. Loads that receive no packet do not affect names.

For example, a run containing both `LD260900` and `ld260900` keeps both logical IDs
and gives each a different mapped filename. A load named `NUL` receives a regular
HTML file. The summary and `packet_drafted` audit entries refer to those actual
files. Monetary calculations, detention eligibility and saved-review writers are
unchanged.

A rerun that changes a packet's filename also changes its existing review evidence
version. Review the new output before saving a decision. The pipeline does not
remove old files left by previous runs; the current summary identifies the current
packet set.

These rules address filename components across ordinary case-insensitive Windows
and case-sensitive systems. They do not change the input loader's business-ID
admission, make the whole output run atomic, validate an untrusted output directory,
protect against concurrent directory replacement, or remove total-path-length
limits. Use an output directory you control, with a stable namespace and sufficient
space.

The Windows behaviors behind this policy are documented in Microsoft's
[Naming Files, Paths, and Namespaces](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file):
case-distinct spellings may identify the same file, and reserved device names remain
reserved when followed by an extension. Original-source native receiving for issue39
demonstrated both silent packet loss cases before this repair.
