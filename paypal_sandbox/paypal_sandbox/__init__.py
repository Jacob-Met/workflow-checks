"""PayPal Sandbox order create/capture integration, behind an explicit flag.

Default is MOCK mode: no network, every response is labeled ``mock=True``.
Real calls require PAYPAL_SANDBOX_ENABLED=1 and sandbox credentials supplied
through the environment. The base URL is fixed to the sandbox host; any live
host is refused. Nothing here creates a live order or captures a live payment.
"""

from .client import (
    LIVE_HOST_MARKERS,
    SANDBOX_BASE_URL,
    PayPalConfigError,
    PayPalSandboxClient,
    PayPalStateError,
)

__all__ = [
    "LIVE_HOST_MARKERS",
    "SANDBOX_BASE_URL",
    "PayPalConfigError",
    "PayPalSandboxClient",
    "PayPalStateError",
]
