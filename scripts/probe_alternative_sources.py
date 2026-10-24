"""Read-only probes of public price charts and historical stock quotes.

PriceHistory requests reproduce the public product page's chart read operation.
The page supplies its own public, temporary chart headers. They are not printed.
No login, subscription, refresh/report call, or anti-bot workaround is used.
Existing snapshots are reused. Saved prices are source quotes, not verified trades.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode


PRICE_PRODUCTS = [
    ("CPU", "cpu", "AMD Ryzen 5 3600", "B07STGGQ18", "USD",
     "https://pricehistory.app/p/amd-ryzen-5-3600-6-core-12-tihFavce"),
    ("RAM", "ram", "Crucial DDR4-3200 16GB CT16G4DFRA32A", "B08C56GZGK", "USD",
     "https://pricehistory.app/p/crucial-16gb-ddr4-ram-3200mhz-pc4-25600-IX5Vsy2h"),
    ("SSD", "ssd", "Samsung 970 EVO Plus 1TB", "B07MFZY2F2", "USD",
     "https://pricehistory.app/p/samsung-970-evo-plus-ssd-1tb-nvme-B1P5Osmb"),
    ("GPU", "gpu", "EVGA RTX 3090 FTW3 Ultra 24G-P5-3987-KR", "B08J5F3G18", "USD",
     "https://pricehistory.app/p/evga-geforce-rtx-3090-ftw3-ultra-gaming-e0up0tw8"),
]


def fetch(url, path, headers=(), post=False):
    if path.exists() and path.stat().st_size:
        return {"cached": True, "file": str(path), "url": url}
    command = ["/usr/bin/curl", "--silent", "--show-error", "--location", "--max-time", "30",
               "-A", "Mozilla/5.0", "-o", str(path), "-w", "%{http_code}"]
    if post:
        command += ["-X", "POST"]
    for header in headers:
        command += ["-H", header]
    result = subprocess.run(command + [url], capture_output=True, text=True, check=False)
    if result.returncode or result.stdout != "200":
        raise RuntimeError(f"Fetch failed: HTTP {result.stdout}, curl {result.returncode}: {url}")
    return {"cached": False, "http_status": result.stdout, "file": str(path), "url": url}


def probe_product(item, raw):
    category, label, name, asin, currency, url = item
    page = raw / f"pricehistory_{label}.html"
    page_request = fetch(url, page)
    source = page.read_text()
    code = re.search(r'FetchHeaders.append\("page","([^"]+)"\)', source).group(1)
    nonce = re.search(r'FetchHeaders.append\("token","([^"]+)"\)', source).group(1)
    endpoint = "https://pricehistory.app/api/price/" + code
    data_path = raw / f"pricehistory_{label}_prices.json"
    data_request = fetch(endpoint, data_path, post=True, headers=(
        "Content-Type: application/json", "page: " + code, "token: " + nonce,
        "Referer: " + url))
    data = json.loads(data_path.read_text())
    assert data["Code"] == code and isinstance(data["History"]["Price"], list)
    title = re.search(r"<h1[^>]*>(.*?)</h1>", source, re.S)
    metadata = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", source, re.S):
        cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S)
        clean = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in cells]
        if len(clean) >= 2 and clean[0] in ("Store Product Code", "Store Name"):
            metadata[clean[0]] = clean[1]
    if asin:
        assert metadata.get("Store Product Code") == asin
        assert metadata.get("Store Name") == "amazon.com"
    return {"category": category, "label": label, "name": name,
            "page_title": html.unescape(re.sub(r"<[^>]+>", "", title.group(1))) if title else None,
            "asin": metadata.get("Store Product Code"), "store": metadata.get("Store Name"),
            "currency": currency, "product_url": url, "chart_url": endpoint,
            "page_request": page_request, "data_request": data_request,
            "raw_file": data_path.name, "source_updated_on": data.get("Price", {}).get("UpdatedOn")}


def probe_stock(symbol, raw):
    start = int(datetime(2020, 1, 1, tzinfo=timezone.utc).timestamp())
    end = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp())
    if symbol.isdigit():
        url = "https://api.finance.naver.com/siseJson.naver?" + urlencode({
            "symbol": symbol, "requestType": 1, "startTime": "20200101",
            "endTime": "20221231", "timeframe": "day"})
        path = raw / f"naver_{symbol}.txt"
    else:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?" + urlencode({
            "period1": start, "period2": end, "interval": "1d", "events": "div|split"})
        path = raw / f"yahoo_{symbol}.json"
    return {"symbol": symbol, **fetch(url, path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--stocks-only", action="store_true")
    args = parser.parse_args()
    raw = args.output / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    summary = {"retrieved_at_utc": datetime.now(timezone.utc).isoformat()}
    if not args.stocks_only:
        summary["pricehistory_products"] = []
        for product in PRICE_PRODUCTS:
            record = probe_product(product, raw)
            summary["pricehistory_products"].append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        summary["stocks"] = list(pool.map(lambda s: probe_stock(s, raw),
                                         ("INTC", "AMD", "MU", "NVDA", "005930", "000660")))
    (args.output / "requests.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print("Stock requests completed:", len(summary["stocks"]))


if __name__ == "__main__":
    main()
