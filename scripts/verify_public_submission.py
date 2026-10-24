"""Verify the public submission using only the Python standard library.

No network calls; no changes to data or manifest; failures return nonzero.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

IGNORED_DIRS = {'.git', '.venv', '__pycache__', '.mplconfig'}
RAW_ALLOW = {
    'data/verification/2026-10-22/crypto/cm_eth_daily_raw.json',
    'data/verification/2026-10-22/crypto/cm_fetch_manifest.json',
}
SECRET = re.compile(r'(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{24,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
LINK = re.compile(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(root, name):
    with (root / name).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def read_json(root, name):
    return json.loads((root / name).read_text(encoding='utf-8'))


def without_fences(text):
    result, fence = [], None
    for line in text.splitlines():
        match = re.match(r'^\s*(`{3,}|~{3,})', line)
        if match:
            char = match[1][0]
            fence = None if fence == char else char
        elif fence is None:
            result.append(line)
    return '\n'.join(result)


def anchors(path):
    found, counts = set(), {}
    for line in without_fences(path.read_text()).splitlines():
        match = re.match(r'^#{1,6}\s+(.+?)\s*#*$', line)
        if not match:
            continue
        name = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', match[1]).lower()
        name = re.sub(r'[^\w\- ]', '', name).replace(' ', '-')
        repeat = counts.get(name, 0)
        found.add(name if repeat == 0 else f'{name}-{repeat}')
        counts[name] = repeat + 1
    found.update(re.findall(r'<(?:a|span)\s+(?:id|name)=[\'\"]([^\'\"]+)', path.read_text()))
    return found


def verify(root):
    files = {}
    for path in root.rglob('*'):
        rel = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in rel.parts) or path.name == '.DS_Store':
            continue
        require(not path.is_symlink(), f'Symlink is not allowed: {rel}')
        if path.is_file():
            files[rel.as_posix()] = path
    manifest = read_json(root, 'PUBLICATION_MANIFEST.json')
    entries = {entry['path']: entry for entry in manifest['files']}
    require(len(entries) == len(manifest['files']), 'Duplicate manifest entry')
    require(set(files) - {'PUBLICATION_MANIFEST.json'} == set(entries), 'Manifest and actual file set differ')
    for name, entry in entries.items():
        require(files[name].stat().st_size == entry['bytes'], f'Size mismatch: {name}')
        require(digest(files[name]) == entry['sha256'], f'SHA mismatch: {name}')
        require(files[name].stat().st_size < 100_000_000, f'GitHub file limit: {name}')
    require({name for name in files if name.startswith('data/verification/')} == RAW_ALLOW,
            'Unexpected or absent third-party raw file')
    for name, path in files.items():
        parts = Path(name).parts
        require(not any(p in {'.openai', '.aws', '.codex', '.agents'} for p in parts), f'Private settings: {name}')
        require(not any(p == '.env' or p.startswith('.env.') for p in parts), f'Environment file: {name}')
        require(path.suffix.lower() not in {'.zip', '.pem', '.key'}, f'Forbidden bundle/key: {name}')
        require(not name.startswith(('dashboard/dist/data/', 'dashboard/dist/reports/')), f'Restricted app data: {name}')
        if path.suffix.lower() not in {'.png'}:
            content = path.read_text(encoding='utf-8')
            require(not SECRET.search(content), f'Credential-shaped content: {name}')
    for name in ('dashboard/dist/index.full.html', 'dashboard/public/index.html',
                 'dashboard/public/public-view.js', 'docs/data_redistribution.md', 'RIGHTS.md'):
        require(name in files, f'Required source/document absent: {name}')
    source_catalog = read_json(root, 'data/source_catalog.json')
    require(len(source_catalog['urls']) > 0, 'Empty source catalog')
    require('CC BY-NC 4.0' in files['RIGHTS.md'].read_text(), 'ETH license notice absent')

    daily = read_csv(root, 'data/processed/2026-10-22/crypto/eth_daily.csv')
    weekly = read_csv(root, 'data/processed/2026-10-22/crypto/eth_weekly.csv')
    require(len(daily) == 1096 and len(weekly) == 156, 'ETH row count mismatch')
    require(daily[0]['date'] == '2020-01-01' and daily[-1]['date'] == '2022-12-31', 'ETH range mismatch')
    from datetime import date, timedelta
    dates = [date.fromisoformat(row['date']) for row in daily]
    require(all(b - a == timedelta(days=1) for a, b in zip(dates, dates[1:])), 'ETH dates not unique/continuous')
    raw_hash = digest(root / 'data/verification/2026-10-22/crypto/cm_eth_daily_raw.json')
    require(all(row['source_sha256'] == raw_hash for row in daily + weekly), 'ETH source hash mismatch')
    require(sum(row['price_return_fraction'] != '' for row in weekly) == 155, 'Weekly return count mismatch')
    flag = lambda key: sum(int(row[key]) for row in daily)
    require((flag('is_partial_transition'), flag('pow_terminated'), flag('unobserved')) == (1, 107, 0), 'ETH status mismatch')
    for column in ('rev_usd_per100mh_gross', 'iss_usd_per100mh'):
        require(sum(row[column] == '' for row in daily) == 108, f'Proxy null count: {column}')
        require(all((row[column] == '') == bool(int(row['is_partial_transition']) or int(row['pow_terminated'])) for row in daily), f'Proxy state mismatch: {column}')
    public = read_json(root, 'data/public/dashboard.json')
    require(public['source']['license'] == 'CC BY-NC 4.0', 'Dashboard license mismatch')
    require(len(public['series']) == 1096, 'Dashboard row count mismatch')
    for expected, actual in zip(daily, public['series']):
        require(actual['date'] == expected['date'], 'Dashboard date mismatch')
        for a, b in (('price_usd', 'price_usd'), ('proxy_a', 'rev_usd_per100mh_gross'), ('proxy_b', 'iss_usd_per100mh')):
            require(actual[a] is None if expected[b] == '' else isinstance(actual[a], (float, int)) and math.isclose(actual[a], float(expected[b]), abs_tol=1e-8), f'Dashboard ETH value mismatch: {a}')
    metrics = read_csv(root, 'data/analysis/2026-10-23/forecast/forecast_metrics.csv')
    fc = public['forecast']
    require(len(metrics) == fc['series'] == 35, 'Forecast series mismatch')
    require(sum(row['passed'].lower() in {'true', '1'} for row in metrics) == fc['passed'] == 0, 'Forecast gate mismatch')
    require(sum(int(row['n']) for row in metrics) == fc['predictionRows'] == 394, 'Forecast evaluation rows mismatch')
    for example in fc['examples']:
        row = next(r for r in metrics if r['id'] == example['id'])
        for key in ('n', 'nonoverlapN', 'brier', 'baselineBrier', 'mae', 'naiveMae', 'ece'):
            require(math.isclose(float(row[key]), example[key], abs_tol=1e-8), f'Forecast aggregate mismatch: {key}')

    links = images = 0
    anchor_cache = {}
    for name, path in files.items():
        if path.suffix != '.md':
            continue
        for match in LINK.finditer(without_fences(path.read_text())):
            target = match[1]
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc:
                continue
            destination = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            require(destination.is_relative_to(root), f'Link outside public tree: {name} -> {target}')
            require(destination.exists(), f'Broken link: {name} -> {target}')
            if parsed.fragment and destination.suffix == '.md':
                if destination not in anchor_cache:
                    anchor_cache[destination] = anchors(destination)
                require(unquote(parsed.fragment) in anchor_cache[destination], f'Broken anchor: {name} -> {target}')
            links += 1
            images += match[0].startswith('!')
    report = files['REPORT.md'].read_text()
    require(len(re.findall(r'!\[', report)) == 13, 'Report image count should be 8 analysis + 2 explanatory + 3 UI')
    print(f'PASS: {len(entries)} manifest files; {links} local Markdown links ({images} images); ETH 1096/156/155; proxies 988+108; forecast 35/0/394')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        verify(args.root.resolve())
    except (ValueError, KeyError, OSError, StopIteration) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        sys.exit(1)
