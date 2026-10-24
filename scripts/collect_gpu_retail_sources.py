"""Cache public 3DCenter 2022 source pages linked by the saved September table.

Explicit acquisition step. Analysis/preprocessing scripts stay offline.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urljoin

from audit_alternative_sources import german_date, html_tables

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "data/feasibility/2026-10-21/alternatives/raw"
OUT = ROOT / "data/verification/2026-10-22/gpu"
BASE = "https://www.3dcenter.org"


def collect():
    OUT.mkdir(parents=True, exist_ok=True)
    source = (OLD / "3dcenter_2022_09_11.html").read_text()
    table = next(t for t in re.findall(r"<table\b[^>]*>.*?</table>", source, re.S | re.I)
                 if "US-MSRP vs" in t)
    items = []
    for href, label in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', table, re.S):
        date = german_date(html.unescape(re.sub(r"<[^>]+>", "", label)), 2022)
        if date.year == 2022:
            items.append((date.isoformat(), urljoin(BASE, href)))

    def one(item):
        date, url = item
        path = OUT / f"3dcenter_{date}.html"
        cached = path.exists() and path.stat().st_size > 0
        if not cached:
            result = subprocess.run(["/usr/bin/curl", "--fail", "--silent", "--show-error",
                "--location", "--max-time", "40", "-A", "Mozilla/5.0", url, "-o", str(path)],
                capture_output=True, text=True)
            if result.returncode:
                return {"date": date, "url": url, "status": "failed", "curl_code": result.returncode}
        data = path.read_bytes()
        if not any(any("3070" in cell for row in table for cell in row)
                   for table in html_tables(path)):
            return {"date": date, "url": url, "status": "unverified_content"}
        return {"date": date, "url": url, "status": "ok", "cached": cached,
                "file": str(path.relative_to(ROOT)), "sha256": hashlib.sha256(data).hexdigest()}

    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(one, items))
    (OUT / "retail_requests.json").write_text(json.dumps({
        "acquired_at_utc": datetime.now(timezone.utc).isoformat(), "requests": records},
        ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(records, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    collect()
