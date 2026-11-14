"""Stage the public dashboard and its public data dependencies for GitHub Pages."""

import argparse
from pathlib import Path
from shutil import copyfile

from verify_public_submission import verify


FILES = (
    'dashboard/public/index.html',
    'dashboard/public/styles.css',
    'dashboard/public/public-view.js',
    'data/public/dashboard.json',
    'data/public/model_comparison.json',
    'data/public/recent_analysis.json',
)

INDEX = """<!doctype html>
<html lang="ko">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="0; url=./dashboard/public/">
<title>PC 부품 가격 관측소</title>
<p><a href="./dashboard/public/">공개 대시보드 열기</a></p>
</html>
"""


def build(source, output):
    source, output = source.resolve(), output.resolve()
    if output.is_relative_to(source) or (output.exists() and any(output.iterdir())):
        raise ValueError('Use an empty output directory outside the public submission.')
    verify(source)
    for name in FILES:
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(source / name, target)
    (output / 'index.html').write_text(INDEX, encoding='utf-8')
    (output / '.nojekyll').touch()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)
