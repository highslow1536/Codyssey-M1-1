"""Assemble the rights-reviewed public edition without changing research files.

The allowlist intentionally excludes raw PC prices, stocks, benchmark tables,
point-by-point predictions, source HTML, and embedded dashboard data/ZIPs.
Use an empty folder or this script's previous output, never the research root.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
SAFE_FIGURES = {
    "docs/assets/figures/01_analysis_flow", "docs/assets/figures/02_observation_coverage",
    "docs/assets/figures/04_forecast_validation", "docs/assets/figures/05_forecast_timeline",
    "data/analysis/2026-10-22/figures/02_correlations",
    "data/analysis/2026-10-22/figures/04_lag_correlations",
    "data/analysis/2026-10-22/figures/05_missing_coverage",
    "data/analysis/2026-10-22/gpu_mining/figures/04_observation_coverage",
}
SAFE_TABLES = {
    "data/analysis/2026-10-22/correlations.csv",
    "data/analysis/2026-10-22/correlations_by_year.csv",
    "data/analysis/2026-10-22/coverage.csv",
    "data/analysis/2026-10-22/lag_correlations.csv",
    "data/analysis/2026-10-22/lag_peaks_exploratory.csv",
    "data/analysis/2026-10-22/sensitivity.csv",
    "data/analysis/2026-10-22/gpu_mining/correlations.csv",
    "data/analysis/2026-10-22/gpu_mining/date_sensitivity.csv",
    "data/analysis/2026-10-23/forecast/forecast_metrics.csv",
}
CM_RAW = {
    "data/verification/2026-10-22/crypto/cm_eth_daily_raw.json",
    "data/verification/2026-10-22/crypto/cm_fetch_manifest.json",
}
SECRET = re.compile(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{24,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")


def allowed(rel):
    p = Path(rel)
    if any(part.startswith(".") or part == "__pycache__" for part in p.parts):
        return False
    if rel.startswith("publication/templates/"):
        return p.suffix == ".in"
    if rel.startswith(("scripts/", "tests/")):
        return p.suffix == ".py"
    if rel.startswith("config/"):
        return p.suffix == ".json"
    if rel.startswith("docs/") and p.suffix == ".md":
        return True
    if rel.startswith("dashboard/"):
        if rel.startswith(("dashboard/dist/data/", "dashboard/dist/reports/")):
            return False
        return p.suffix in (".html", ".js", ".css", ".svg", ".mjs", ".md") or rel == "dashboard/package.json"
    if rel in SAFE_TABLES or rel in CM_RAW:
        return True
    if rel.startswith("data/processed/2026-10-22/crypto/"):
        return p.suffix in (".csv", ".json", ".md")
    if rel.startswith("data/public/"):
        return p.suffix in (".csv", ".json", ".md")
    if rel.startswith("data/verification/") and p.suffix == ".md":
        return False
    if rel.startswith("data/") and p.suffix == ".md":
        return True
    if rel.startswith("docs/assets/public/"):
        return p.suffix in (".png", ".svg")
    if p.suffix in (".png", ".svg") and str(p.with_suffix("")) in SAFE_FIGURES:
        return True
    return rel in {"README.md", "REPORT.md", "RIGHTS.md", "requirements-analysis.txt"}


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def classify(rel):
    if rel.startswith(('data/public/model_comparison', 'docs/assets/public/04_model_comparison',
                       'docs/assets/public/05_model_coverage', 'data/public/recent_',
                       'data/public/source_freshness', 'docs/assets/public/06_recent_analysis',
                       'docs/assets/public/07_report_summary', 'docs/assets/public/08_missing_values_guide')):
        return 'project-authored non-reconstructive analysis and validation aggregates; not Coin Metrics ETH data'
    if "crypto/" in rel or rel.startswith("docs/assets/public/0") or rel.startswith("data/public/"):
        return "Coin Metrics ETH / CC BY-NC 4.0 or documented aggregate"
    if rel in SAFE_TABLES or Path(rel).suffix in (".png", ".svg"):
        return "original non-reconstructive statistics or explanatory figure"
    return "project-authored code or public-edition documentation"


def assemble(output):
    output = output.resolve()
    if output == ROOT or ROOT.is_relative_to(output) or output.is_symlink():
        raise ValueError("Output must be a separate, non-symlink folder")
    marker = output / "PUBLICATION_MANIFEST.json"
    if output.exists() and any(p.name != ".git" for p in output.iterdir()) and not marker.exists():
        raise ValueError("Output is neither empty nor a previous public build")
    previous = json.loads(marker.read_text())["files"] if marker.exists() else []
    # Only files owned by the previous build are replaced; .git is preserved.
    for entry in previous:
        target = output / entry["path"]
        if target.is_file():
            target.unlink()
    output.mkdir(parents=True, exist_ok=True)
    sources = []
    for p in ROOT.rglob("*"):
        if not p.is_file() or output in p.parents or p.is_symlink():
            continue
        rel = p.relative_to(ROOT).as_posix()
        if allowed(rel):
            sources.append(p)
    for p in sources:
        target = output / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    for p in (ROOT / "publication/templates").rglob("*.in"):
        target = output / p.relative_to(ROOT / "publication/templates").with_suffix("")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    # Preserve the exact regression criterion without embedding eight raw quote rows.
    price_test = output / "tests/test_domestic_current.py"
    test_source = price_test.read_text()
    expected_line = re.search(r"  expected=(\[.*\])\n", test_source)
    if expected_line:
        import ast
        expected = ast.literal_eval(expected_line[1])
        expected_digest = hashlib.sha256(json.dumps(expected, separators=(",", ":")).encode()).hexdigest()
        test_source = test_source.replace(expected_line[0], "  observed=[]  # Public edition: compare the original expectation by SHA-256.\n")
        test_source = test_source.replace("for p,wanted in zip(self.data['products'],expected):", "for p in self.data['products']:")
        test_source = test_source.replace("self.assertEqual(tuple(q[k] for k in ['productPrice','shipping','deliveredPrice']),wanted)", "observed.append(tuple(q[k] for k in ['productPrice','shipping','deliveredPrice']))")
        marker_line = " def test_hidden_footer_price_is_not_charged(self):"
        check = f"  self.assertEqual(hashlib.sha256(json.dumps(observed,separators=(',',':')).encode()).hexdigest(),'{expected_digest}')\n"
        test_source = test_source.replace(marker_line, check + marker_line)
        price_test.write_text(test_source)
    (output / ".gitignore").write_text(".venv/\n__pycache__/\n*.pyc\n.mplconfig/\n.DS_Store\nsubmission-public/\n.env\n.env.*\n")
    # Do not make the full app fail with an unexplained missing-data error.
    full_index = output / "dashboard/dist/index.html"
    original_index = ROOT / "dashboard/dist/index.full.html"
    if not original_index.exists():
        original_index = ROOT / "dashboard/dist/index.html"
    shutil.copyfile(original_index, output / "dashboard/dist/index.full.html")
    full_index.write_text('''<!doctype html><html lang="ko"><meta charset="utf-8"><title>공개 제출판 안내</title>
<meta http-equiv="refresh" content="0;url=../public/"><p>공개 데이터 대시보드로 이동합니다. <a href="../public/">공개 화면 열기</a></p>
<p>기존 전체 화면 코드는 index.full.html이며 실행에 별도 허가 원본이 필요합니다.</p></html>''')
    full_reproduction = output / "docs/full_reproduction.md"
    if not (ROOT / "docs/full_reproduction.md").exists():
        original_reproduction = (ROOT / "docs/reproduction.md").read_text().replace("submission_checklist.md#3-github-제출-전에-남은-작업", "submission_checklist.md")
        full_reproduction.write_text("> 원래 전체 스냅샷용 순서입니다. 공개판에는 필요한 부품·주가 원본이 없으므로 아래 전체 순서를 실행할 수 없습니다. 공개 자료만으로 실행하는 순서는 [공개판 재현 안내](reproduction.md)를 따릅니다. 수집 코드의 공개는 수집·재배포 허가가 아닙니다.\n\n" + original_reproduction)

    excluded = []
    for folder in (ROOT / "data", ROOT / "docs/assets", ROOT / "dashboard/dist/data", ROOT / "dashboard/dist/reports", ROOT / "dashboard/qa"):
        for p in folder.rglob("*"):
            if p.is_file() and not p.is_symlink() and not allowed(p.relative_to(ROOT).as_posix()):
                excluded.append({"path": p.relative_to(ROOT).as_posix(), "bytes": p.stat().st_size,
                                 "sha256": digest(p), "reason": "source redistribution permission absent/unclear, reconstructive data, or embedded bundle"})
    # Inventory contains no response bodies or prices.
    with (output / "data/excluded_inventory.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=("path", "bytes", "sha256", "reason"))
        w.writeheader()
        w.writerows(sorted({r["path"]: r for r in excluded}.values(), key=lambda r: r["path"]))
    url_pattern = re.compile(r'https?://[^\s<>"\)\]\}]+')
    urls = set()
    for p in ROOT.joinpath("docs").glob("*.md"):
        for value in url_pattern.findall(p.read_text()):
            parsed = urlsplit(value)
            if not parsed.username and not re.search(r"(?:token|signature|api_key|secret|password)=", parsed.query, re.I):
                urls.add(urlunsplit(parsed))
    (output / "data/source_catalog.json").write_text(json.dumps({"checked": "2026-10-25", "note": "Source URLs only; access is not a redistribution license. Rights review remains dated 2026-10-24.", "urls": sorted(urls)}, ensure_ascii=False, indent=2) + "\n")

    # Missing source links become an explicit access note, never a fake CSV.
    link_pattern = re.compile(r"(!?)\[([^\]]*)\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")
    redirects = []
    for p in output.rglob("*.md"):
        text = p.read_text()
        if p.relative_to(output).as_posix() not in {"README.md", "REPORT.md", "docs/submission_checklist.md", "docs/reproduction.md", "docs/assets/README.md", "data/README.md", "docs/data_redistribution.md"}:
            text = "> 공개판 안내: 작성 당시 연구 기록입니다. 원가격·주가·벤치마크 원본과 복원 가능한 파일은 제외했습니다. 현재 공개 범위·실행법은 루트 README와 데이터 이용 안내를 따릅니다.\n\n" + text
        def replace(match):
            image, label, href = match.groups()
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", href) or href.startswith("#"):
                return match.group(0)
            name, _, fragment = href.partition("#")
            target = (p.parent / name).resolve()
            if target.exists() or target in {output / "PUBLICATION_MANIFEST.json", output / "data/references_omitted.json"}:
                return match.group(0)
            redirects.append({"document": p.relative_to(output).as_posix(), "omitted_reference": href})
            note = os.path.relpath(output / "data/README.md", p.parent).replace(os.sep, "/") + "#excluded"
            if image:
                return f"> **공개 제외 그림:** {label}. 원시 시계열·견적을 복원할 수 있어 포함하지 않았습니다. [제외 자료 안내]({note})"
            return f"[{label} — 원본 미포함]({note})"
        text = link_pattern.sub(replace, text)
        p.write_text(text)
    (output / "data/references_omitted.json").write_text(json.dumps(redirects, ensure_ascii=False, indent=2) + "\n")
    files = []
    for p in sorted(output.rglob("*")):
        if not p.is_file() or any(part in {".git", ".venv", "__pycache__", ".mplconfig"} for part in p.parts) or p.name == ".DS_Store" or p == marker:
            continue
        rel = p.relative_to(output).as_posix()
        if p.suffix not in (".png", ".zip"):
            try:
                content = p.read_text()
            except UnicodeError:
                raise ValueError(f"Unexpected binary: {rel}")
            if SECRET.search(content):
                raise ValueError(f"Credential-shaped content detected: {rel}")
        files.append({"path": rel, "bytes": p.stat().st_size, "sha256": digest(p), "basis": classify(rel)})
    marker.write_text(json.dumps({"edition": "public-submission", "date": "2026-10-25", "rightsReviewDate": "2026-10-24", "repository": "https://github.com/highslow1536/Codyssey-M1-1", "files": files}, ensure_ascii=False, indent=2) + "\n")
    print(f"Public edition: {len(files)} files; {len(excluded)} excluded inventory entries; {len(redirects)} references explained")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "submission-public")
    assemble(parser.parse_args().output)
