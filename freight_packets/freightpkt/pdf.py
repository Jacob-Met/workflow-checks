"""Optional HTML -> PDF using a locally installed Edge/Chrome in headless mode.

No Python dependency and no network. If no browser is found we simply keep
the HTML (which prints cleanly to PDF from any browser).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_browser() -> str | None:
    env = os.environ.get("POC_BROWSER")
    if env and Path(env).exists():
        return env
    for c in _CANDIDATES:
        if Path(c).exists():
            return c
    for name in ("msedge", "chrome", "chromium", "google-chrome"):
        p = shutil.which(name)
        if p:
            return p
    return None


def html_to_pdf(html_path: Path, pdf_path: Path, timeout: int = 60) -> bool:
    browser = find_browser()
    if not browser:
        return False
    html_path, pdf_path = Path(html_path).resolve(), Path(pdf_path).resolve()
    cmd = [browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
           f"--print-to-pdf={pdf_path}", html_path.as_uri()]
    try:
        subprocess.run(cmd, check=False, timeout=timeout, capture_output=True)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return pdf_path.exists() and pdf_path.stat().st_size > 0
