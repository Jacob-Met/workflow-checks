"""PT authorization / visit-limit tracker (proof of concept).

SYNTHETIC DATA ONLY. Stdlib-only. Produces a daily re-authorization worklist
from a schedule export, an authorization log and a per-payer rules table.
Nothing is sent to payers; every output is a draft for staff.
"""

__version__ = "0.1.0"
