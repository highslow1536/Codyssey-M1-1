#!/usr/bin/env python3
"""Bounded, public GET snapshots of the eight already selected Danawa SKUs.

--fetch collects once into a new snapshot folder; otherwise processes saved
responses offline. No checkout, login, seller bridge, or UI-hidden price is
treated as a verified transaction price. Historical inputs remain unchanged.
"""
import argparse
import csv
import hashlib
import html
import json
import re
import subprocess
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
KST = ZoneInfo("Asia/Seoul")
DEFAULT = ROOT / "data/verification/2026-10-23/domestic"
OUTPUT = ROOT / "data/processed/2026-10-23/domestic"
PRODUCTS = list(csv.DictReader((ROOT / "data/processed/2026-10-21/domestic/products.csv").open(encoding="utf-8-sig")))


def plain(markup):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", markup))).strip()


class Inputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "input" and a.get("id"):
            self.inputs[a["id"]] = a.get("value", "")


def integer(value):
    return int(str(value).replace(",", "")) if re.fullmatch(r"[\d,]+", str(value)) else None


def parse_pc(source, code):
    inputs = Inputs()
    inputs.feed(source)
    values = inputs.inputs
    product = integer(values.get("min_price_" + code))
    base = integer(values.get("intMinFee"))
    total = integer(values.get("intIncludeDeliveryFee"))
    assert product and base == product, (code, "summary price does not reconcile")
    # The page explicitly exposes these fields for its delivery toggle. Do
    # not use topFixDeliveryIncludeFee, a hidden display string which can be
    # internally inconsistent with intIncludeDeliveryFee.
    shipping = total - product if total is not None and total >= product else None
    count = re.search(r'id="priceCompareTabCount"[^>]*>([\d,]+)', source)
    specs = re.search(r'<div[^>]*class="[^"]*spec_list[^"]*"[^>]*>(.*?)</div>', source, re.S)
    # Published current-page quote, not a claim that every merchant is in
    # stock or that checkout/rebate conditions have been verified.
    offers = []
    group = re.search(r'<ul class="list__mall-price">(.*?)</ul>', source, re.S)
    for item in re.findall(r'<li class="list-item">(.*?)</li>', group[1] if group else "", re.S):
        price = re.search(r'class="text__num">([\d,]+)</span>', item)
        seller = re.search(r'<img[^>]*alt=[\'\"]([^\'\"]+)', item)
        if not seller:
            seller = re.search(r'class="box__logo">(.*?)</div>', item, re.S)
        if price:
            offers.append({"seller": plain(seller[1]) if seller else None,
                           "productPrice": integer(price[1]),
                           "shipping": shipping if not offers else None,
                           "shippingVerified": not offers and shipping is not None,
                           "cashOnly": 'badge__cash' in item,
                           "isLowestLabel": 'badge__lowest' in item})
    assert offers and offers[0]["productPrice"] == product, (code, "first offer differs")
    return {"productPrice": product, "shipping": shipping, "deliveredPrice": total,
            "shippingBasis": "source_intIncludeDeliveryFee_minus_intMinFee",
            "displayedSellerCount": integer(count[1]) if count else None,
            "observedOffers": offers, "observedOfferCount": len(offers),
            "priceBasis": "PC_ordinary_lowest_no_membership_or_specific_card_benefit",
            "paymentBasis": "ordinary_listing_cash_only_separate",
            "merchantCheckoutVerified": False,
            "sourcePriceUpdatedAt": None,
            "specText": plain(specs[1]) if specs else None,
            "discontinuedWarning": "단종된 모델" in source,
            "notes": ["요약 상품가+원문 배송 포함 금액을 분리. 특정 카드·멤버십·적립금 혜택 제외.",
                      "몰 수는 다나와 표시 판매처 수이며 독립 재고·결제 가능 판매처를 전수 확인한 수가 아님.",
                      "숨겨진 topFixDeliveryIncludeFee 문자열은 가격 산정에 사용하지 않음."]}


def parse_mobile_series(source, code):
    """CSR main quote is absent: same-SKU server-rendered series cell only."""
    cell = re.search(r'id="series-minPrice-' + re.escape(code) + r'"(.*?)</a>', source, re.S)
    price = re.search(r'class="text__number">([\d,]+)</span>', cell[1] if cell else "")
    return integer(price[1]) if price else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT)
    args = parser.parse_args()
    raw = args.snapshot / "raw"
    manifest_file = args.snapshot / "manifest.json"
    if args.fetch:
        if manifest_file.exists():
            raise SystemExit("Snapshot already has a manifest; use a new --snapshot directory.")
        raw.mkdir(parents=True, exist_ok=True)
        entries = []
        for p in PRODUCTS:
            code = p["product_code"]
            for surface, url in (("pc", p["product_url"]), ("mobile", f"https://m2.danawa.com/product/product.html?code={code}")):
                target = raw / (code + ("" if surface == "pc" else "_mobile") + ".html")
                if not target.exists():
                    result = subprocess.run(["/usr/bin/curl", "--location", "--max-time", "30", "--silent", "--show-error", "-H", "User-Agent: Mozilla/5.0", url, "-o", str(target), "-w", "%{http_code}"], capture_output=True, text=True)
                    if result.returncode or result.stdout != "200":
                        raise RuntimeError((surface, code, result.returncode, result.stdout))
                entries.append({"code": code, "surface": surface, "url": url,
                                "file": str(target.relative_to(args.snapshot)),
                                "collectedAt": datetime.fromtimestamp(target.stat().st_mtime, KST).isoformat(timespec="seconds"),
                                "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
        manifest_file.write_text(json.dumps({"entries": entries, "method": "public GET; eight selected SKUs, PC/mobile once each"}, ensure_ascii=False, indent=2) + "\n")
    manifest = json.loads(manifest_file.read_text())
    quotes = []
    for p in PRODUCTS:
        entry = next(x for x in manifest["entries"] if x["code"] == p["product_code"] and x["surface"] == "pc")
        path = args.snapshot / entry["file"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        quote = parse_pc(path.read_text(), p["product_code"])
        mobile_entry = next(x for x in manifest["entries"] if x["code"] == p["product_code"] and x["surface"] == "mobile")
        mobile = args.snapshot / mobile_entry["file"]
        assert hashlib.sha256(mobile.read_bytes()).hexdigest() == mobile_entry["sha256"]
        mobile_price = parse_mobile_series(mobile.read_text(encoding="cp949", errors="replace"), p["product_code"])
        quote["mobileCheck"] = {"productPrice": mobile_price,
            "match": mobile_price == quote["productPrice"] if mobile_price is not None else None,
            "basis": "same_product_series_cell; main_CSR_quote_not_observed",
            "sourceUrl": mobile_entry["url"], "collectedAt": mobile_entry["collectedAt"],
            "sha256": mobile_entry["sha256"]}
        quote.update({"id": p["product_code"], "category": p["category"], "name": p["name"],
                      "sourceUrl": entry["url"], "collectedAt": entry["collectedAt"],
                      "sourceSha256": entry["sha256"], "currency": "KRW"})
        quotes.append(quote)
        print(p["product_code"], quote["productPrice"], "+", quote["shipping"], "=", quote["deliveredPrice"], "KRW", "sellers", quote["displayedSellerCount"])
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "quotes.json").write_text(json.dumps({"quotes": quotes, "snapshot": "2026-10-23", "sourceSnapshot": str(args.snapshot.relative_to(ROOT))}, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
