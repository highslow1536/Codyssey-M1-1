"""Audit current availability into a NEW immutable snapshot; never replace history.

One public-page/chart request per existing overseas listing, one chart request
per market, and one PC-page GET per original domestic SKU. No login or retry.
Session headers are never logged; transient unredacted pages are removed even
on failure. Source timestamps, not this check's date, determine data freshness.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from zoneinfo import ZoneInfo

import build_forecast as forecast
import collect_forecast_overseas as prices
import collect_recent_markets as markets
import collect_domestic_quotes as domestic

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def overseas_one(series, folder, as_of, checked):
    label = series['id']
    target = dict(label=label, category=series['category'], domestic_pcode='',
                  domestic_name='', overseas_name=series['name'],
                  url=series['sourceUrl'], currency=series['currency'],
                  condition=series['condition'], same_sku_note='same source listing; no domestic substitution')
    result = {k: series[k] for k in ('id', 'name', 'category', 'currency', 'sourceUrl')}
    result['kind'] = 'overseas'
    result['previousLastWeeklyObservation'] = max(
        (p['date'] for p in series['points'] if p['price'] is not None), default=None)
    try:
        rec = prices.collect_one(target, folder, checked, checked)
        expected = label.split('__')[0].removeprefix('US_').removeprefix('IN_')
        if rec['store_code'] != expected:
            raise ValueError('source product code does not match the existing listing')
        raw = folder / rec['files']['prices']
        payload = json.loads(raw.read_text())
        accepted, excluded = forecast.normalize_quotes(payload['History']['Price'], label,
                                                        5 if series['currency'] == 'USD' else 0)
        days = sorted({p['date'].isoformat() for p in accepted if p['date'] <= as_of})
        result.update(status='ok' if days else 'no_valid_observations',
                      rawFile=str(raw.relative_to(ROOT)), sha256=digest(raw),
                      n=len(accepted), excludedN=len(excluded),
                      firstDate=days[0] if days else None, lastDate=days[-1] if days else None,
                      sourceUpdatedOn=rec.get('source_updated_on'))
    except Exception as exc:
        # Exceptions from these helpers contain status/schema only, no headers.
        result.update(status='failed', reason=f'{type(exc).__name__}: {str(exc)[:250]}')
    finally:
        transient = folder / f'{label}_page.html'
        if transient.exists():
            transient.unlink()
    return result


def domestic_one(product, folder, checked):
    code = product['product_code']
    raw = folder / f'{code}.html'
    result = dict(id='KR_' + code, name=product['name'], category=product['category'],
                  currency='KRW', kind='domestic_spot', sourceUrl=product['product_url'])
    proc = subprocess.run(['/usr/bin/curl', '--silent', '--show-error', '--location',
                           '--max-time', '30', '-A', 'Mozilla/5.0', '-o', str(raw),
                           '-w', '%{http_code}', product['product_url']],
                          capture_output=True, text=True, check=False)
    if proc.returncode or proc.stdout != '200':
        return result | dict(status='failed', reason=f'HTTP {proc.stdout}; curl {proc.returncode}')
    try:
        quote = domestic.parse_pc(raw.read_text(), code)
        # This is a newly viewed offer, not a historical chart observation.
        result.update(status='ok', checkedAt=checked, sourceUpdatedOn=None,
                      rawFile=str(raw.relative_to(ROOT)), sha256=digest(raw),
                      displayedSellerCount=quote['displayedSellerCount'],
                      historicalObservationAdded=False)
    except Exception as exc:
        result.update(status='failed', reason=f'{type(exc).__name__}: price fields did not reconcile')
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--as-of', type=date.fromisoformat, required=True)
    ap.add_argument('--fetch', action='store_true')
    args = ap.parse_args()
    folder = ROOT / 'data/verification' / args.as_of.isoformat() / 'report_refresh'
    marker = folder / 'manifest.json'
    if not args.fetch:
        print(json.dumps(json.loads(marker.read_text())['summary'], ensure_ascii=False))
        return
    if marker.exists():
        raise SystemExit('Snapshot exists; offline inspection is supported, overwriting is not.')
    folder.mkdir(parents=True, exist_ok=True)
    checked = datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds')
    forecast.AS_OF = args.as_of
    series, _, _ = forecast.load_sources()
    overseas = [s for s in series if s['frequency'] == 'weekly']
    for sub in ('overseas', 'markets', 'domestic'):
        (folder / sub).mkdir(exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        price_records = list(pool.map(lambda s: overseas_one(s, folder/'overseas', args.as_of, checked), overseas))
    # Include only calendar days certainly complete before the KST as-of day.
    # This is conservative for UTC crypto days and US exchange closes.
    end = args.as_of - timedelta(days=2)
    markets.RAW_DIR = folder / 'markets'
    markets.RANGE_END = end.isoformat()
    markets.PERIOD2 = int(datetime.combine(end + timedelta(days=1), time(), timezone.utc).timestamp())
    market_series = []
    for cfg in markets.SYMBOLS:
        s = markets.build_series(cfg, checked)
        market_series.append(s)
    (folder/'markets.json').write_text(json.dumps({'asOf': end.isoformat(), 'series': market_series}, ensure_ascii=False, indent=2)+'\n')
    market_records = [dict(id=s['id'], name=s['name'], kind='market', currency=s['currency'],
                           status='ok' if s['nValid'] else 'failed', sourceUrl=s['sourceUrl'],
                           n=s['nValid'], firstDate=s['firstDate'], lastDate=s['lastDate'],
                           rawFile=s['rawFile'], sha256=s['sha256'],
                           reason=None if s['nValid'] else s['fetch']) for s in market_series]
    with ThreadPoolExecutor(max_workers=3) as pool:
        spot_records = list(pool.map(lambda p: domestic_one(p, folder/'domestic', checked), domestic.PRODUCTS))
    records = price_records + market_records + spot_records
    summary = {kind: {'attempted': sum(r['kind']==kind for r in records),
                      'ok': sum(r['kind']==kind and r['status']=='ok' for r in records)}
               for kind in ('overseas', 'market', 'domestic_spot')}
    doc = dict(asOf=args.as_of.isoformat(), checkedAt=checked,
               marketRequestedEnd=end.isoformat(), records=records, summary=summary,
               limitations=['Availability audit only; frozen model benchmark is unchanged.',
                            'A new check is not a new source observation; failed checks do not extend history.',
                            'Domestic spot offers are never appended to monthly chart history.',
                            'Public page/chart calls only; no retries or access-control workarounds.'])
    marker.write_text(json.dumps(doc, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
