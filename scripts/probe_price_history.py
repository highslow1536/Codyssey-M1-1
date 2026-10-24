"""Small, read-only feasibility probe of Danawa's public product price charts.

The request route and parameters were read from the product page's own
summary.min.js. This is an undocumented website endpoint, not a supported API.
Only the five periods exposed by the website UI are queried. No date-range
enumeration, authentication, or access-control bypass is used.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import time
from zoneinfo import ZoneInfo


PRODUCTS = [
    ("CPU", "21694499", "AMD Ryzen 5 7500F, multipack genuine"),
    ("CPU", "76555634", "Intel Core i5-14400F, valuepack genuine"),
    ("RAM", "11790199", "Samsung DDR4-3200 16GB, one module"),
    ("RAM", "18911780", "Samsung DDR5-5600 16GB, one module"),
    ("SSD", "18297002", "Samsung 990 PRO 1TB, without heatsink"),
    ("SSD", "17001050", "SK hynix Platinum P41 1TB"),
    ("GPU", "20740013", "MSI RTX 4060 VENTUS 2X BLACK OC D6 8GB"),
    ("GPU", "76550837", "MSI RTX 5070 Ti VENTUS 3X OC D7 16GB"),
]
PERIODS = (1, 3, 6, 12, 24)
ROUTE = "https://m2.danawa.com/product/getPriceTendencyGraph.json"
DESKTOP_ROUTE = "https://prod.danawa.com/info/ajax/getProductPriceList.ajax.php"


def probe_desktop(output):
    """The desktop UI requests all five chart periods in one response."""
    raw_dir = output / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "checked_date_kst": datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat(),
        "route": DESKTOP_ROUTE,
        "source_script": "https://prod.danawa.com/info/js/common.min.js?v=2610081500",
        "products": [],
    }
    for category, code, name in PRODUCTS:
        path = raw_dir / f"{code}.json"
        url = f"{DESKTOP_ROUTE}?productCode={code}"
        response = subprocess.run([
            "/usr/bin/curl", "--location", "--max-time", "25",
            "--silent", "--show-error",
            "-H", "Accept: application/json, text/javascript, */*; q=0.01",
            "-H", f"Referer: https://prod.danawa.com/info/?pcode={code}",
            "-H", "User-Agent: Mozilla/5.0", url, "-o", str(path),
            "-w", "%{http_code}",
        ], capture_output=True, text=True, check=False)
        record = {
            "category": category, "product_code": code, "name": name,
            "url": url, "http_status": response.stdout,
            "curl_exit_code": response.returncode, "periods": [],
        }
        try:
            if response.returncode:
                raise RuntimeError(response.stderr.strip())
            data = json.loads(path.read_bytes())
            for months in PERIODS:
                group = data[str(months)]
                rows = group["result"]
                record["periods"].append({
                    "period_months": months, "actual_rows": len(rows),
                    "source_count": group["count"],
                    "first": rows[0] if rows else None,
                    "last": rows[-1] if rows else None,
                })
        except (OSError, ValueError, KeyError, RuntimeError, TypeError) as error:
            record["error"] = str(error)
        summary["products"].append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)
        (output / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--desktop", action="store_true")
    args = parser.parse_args()
    if args.desktop:
        probe_desktop(args.output)
        return
    raw_dir = args.output / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "checked_date_kst": datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat(),
        "route": ROUTE,
        "request_method": "GET",
        "source_script": "https://m2.danawa.com/minjs/service/productBlog/summary.min.js?ver=1.9.607",
        "notes": [
            "Actual counts refer to graphDataList rows, not totalCount.",
            "Date labels and minPrice are preserved exactly as returned.",
            "The current price appended by the browser is not a historical row.",
            "Period labels alone do not establish aggregation semantics.",
            "Endpoint accessibility does not establish redistribution rights.",
        ],
        "products": [],
    }
    for category, code, name in PRODUCTS:
        product = {
            "category": category,
            "product_code": code,
            "name": name,
            "product_url": f"https://prod.danawa.com/info/?pcode={code}",
            "periods": [],
        }
        for months in PERIODS:
            path = raw_dir / f"{code}_{months}m.json"
            url = f"{ROUTE}?productCode={code}&period={months}"
            result = subprocess.run(
                [
                    "/usr/bin/curl", "--location", "--max-time", "25",
                    "--silent", "--show-error",
                    "-H", "Accept: application/json, text/javascript, */*; q=0.01",
                    "-H", "Content-Type: application/x-www-form-urlencoded;charset=EUC-KR",
                    "-H", f"Referer: https://m2.danawa.com/product/product.html?code={code}",
                    "-H", "User-Agent: Mozilla/5.0",
                    url, "-o", str(path),
                    "-w", "%{http_code}\n%{content_type}",
                ],
                capture_output=True, text=True, check=False,
            )
            status = result.stdout.splitlines()
            record = {
                "period_months": months,
                "url": url,
                "raw_file": str(path.relative_to(args.output)),
                "http_status": status[0] if status else None,
                "content_type": status[1] if len(status) > 1 else None,
                "curl_exit_code": result.returncode,
            }
            try:
                if result.returncode:
                    raise RuntimeError(result.stderr.strip())
                data = json.loads(path.read_bytes())
                rows = data["graphDataList"]
                labels = [row["date"] for row in rows]
                record.update({
                    "actual_rows": len(rows),
                    "unique_date_labels": len(set(labels)),
                    "source_totalCount": data.get("totalCount"),
                    "first": rows[0] if rows else None,
                    "last": rows[-1] if rows else None,
                    "all_positive_prices": all(isinstance(row.get("minPrice"), (int, float)) and row["minPrice"] > 0 for row in rows),
                })
            except (OSError, ValueError, KeyError, RuntimeError, TypeError) as error:
                record["error"] = str(error)
            product["periods"].append(record)
            print(json.dumps({"code": code, **record}, ensure_ascii=False), flush=True)
            time.sleep(0.5)
        summary["products"].append(product)
        (args.output / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
