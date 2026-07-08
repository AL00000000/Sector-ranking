# -*- coding: utf-8 -*-
"""Kabutan 東証【業種別】騰落ランキングを取得し、業種名と前日比率を保存する。

出力:
  history/YYYY-MM-DD.json       … 当日の生データ(翌日以降の比較用)
  output/sector_ranking_YYYY-MM-DD.csv … 当日のCSV(UTF-8)
  docs/data/YYYY-MM-DD.json     … GitHub Pages 用データ
  docs/data/index.json          … 日付一覧(新しい順)
  標準出力に CSV のフルパスを表示する。
"""
import json
import re
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

BASE = Path(__file__).parent
HISTORY = BASE / "history"
OUTPUT = BASE / "output"
DOCS_DATA = BASE / "docs" / "data"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
URL = "https://kabutan.jp/warning/?mode=9_1&market=0&capitalization=-1&stc=zenhiritsu&stm=1&col=zenhiritsu"
COOKIE = "shared_perpage=50"
EXPECTED_COUNT = 33

AS_OF_RE = re.compile(r'(\d{4})年(\d{2})月(\d{2})日</li>\s*<li>(\d{2}:\d{2})現在')

def _cell(group: str) -> str:
    return rf'<td[^>]*>\s*(?:<span[^>]*>)?(?P<{group}>[^<]*)(?:</span>)?\s*%?\s*</td>'

_ICON = r'(?:(?!</td>)[\s\S])*</td>'
_EMPTY_CELL = r'<td[^>]*>\s*</td>'
ROW_RE = re.compile(
    r'<tr>\s*'
    r'<td class="tac"><a href="/stock/\?code=(?P<code>[0-9A-Z]+)">[0-9A-Z]+</a></td>\s*'
    r'<th scope="row" class="tal"><a href="/themes/\?industry=[^"]+">(?P<industry>[^<]+)</a></th>\s*'
    r'<td>(?P<issue_count>[^<]*)</td>\s*'
    r'<td class="chart_icon">' + _ICON + r'\s*'
    + _cell('price') + r'\s*'
    + _EMPTY_CELL + r'\s*'
    + _cell('change') + r'\s*'
    + _cell('change_pct') + r'\s*'
    + _cell('per') + r'\s*'
    + _cell('pbr') + r'\s*'
    + _cell('yield_pct'))


def parse_number(s: str) -> float:
    try:
        return float(str(s).replace(",", "").replace("+", "").replace("－", "0"))
    except (ValueError, TypeError):
        return 0.0


def fetch() -> str:
    req = urllib.request.Request(URL, headers={"User-Agent": UA, "Cookie": COOKIE})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", errors="replace")


def parse(html: str):
    body = html.split('<div class="warning_contents">', 1)[-1]
    body = body.split('</tbody>', 1)[0]
    rows = []
    for m in ROW_RE.finditer(body):
        d = {k: v.strip() for k, v in m.groupdict().items()}
        rows.append({
            "industry": d["industry"],
            "change_pct": d["change_pct"],
        })
    return rows


def add_comparisons(rows, today: str):
    prev_files = sorted(p for p in HISTORY.glob("*.json") if p.stem < today)
    prev_date = None
    prev_data = {}
    if prev_files:
        prev_date = prev_files[-1].stem
        prev = json.loads(prev_files[-1].read_text(encoding="utf-8-sig"))
        prev_data = {s["industry"]: {"rank": s["rank"], "change_pct": s["change_pct"]} for s in prev}

    for s in rows:
        prev = prev_data.get(s["industry"])
        if prev:
            diff = prev["rank"] - s["rank"]
            s["move"] = f"↑{diff}" if diff > 0 else f"↓{-diff}" if diff < 0 else "→"
            s["prev_rank"] = prev["rank"]
            s["move_num"] = diff
            s["is_new"] = False
            delta = parse_number(s["change_pct"]) - parse_number(prev["change_pct"])
            s["change_pct_diff_num"] = round(delta, 2)
            s["change_pct_diff"] = f"{delta:+.2f}%" if delta else "0.00%"
        else:
            s["move"] = "NEW" if prev_data else ""
            s["prev_rank"] = ""
            s["move_num"] = None
            s["is_new"] = bool(prev_data)
            s["change_pct_diff_num"] = None
            s["change_pct_diff"] = ""
    return prev_date


def main():
    today = date.today().isoformat()
    HISTORY.mkdir(exist_ok=True)
    OUTPUT.mkdir(exist_ok=True)
    DOCS_DATA.mkdir(parents=True, exist_ok=True)

    html = fetch()
    m = AS_OF_RE.search(html)
    as_of = f"{m.group(1)}-{m.group(2)}-{m.group(3)} {m.group(4)}" if m else None
    rows = parse(html)
    if len(rows) != EXPECTED_COUNT:
        print(f"ERROR: expected {EXPECTED_COUNT} rows, got {len(rows)}", file=sys.stderr)
        sys.exit(1)

    seen = set()
    rows = [s for s in rows if not (s["industry"] in seen or seen.add(s["industry"]))]
    if len(rows) != EXPECTED_COUNT:
        print(f"ERROR: expected {EXPECTED_COUNT} unique industries, got {len(rows)}", file=sys.stderr)
        sys.exit(1)
    for i, s in enumerate(rows, 1):
        s["rank"] = i

    prev_date = add_comparisons(rows, today)

    (HISTORY / f"{today}.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    payload = {"date": today, "as_of": as_of, "prev_date": prev_date, "count": len(rows), "rows": rows}
    (DOCS_DATA / f"{today}.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    dates = sorted((p.stem for p in DOCS_DATA.glob("????-??-??.json")), reverse=True)
    (DOCS_DATA / "index.json").write_text(
        json.dumps({"dates": dates}, ensure_ascii=False), encoding="utf-8")

    csv_path = OUTPUT / f"sector_ranking_{today}.csv"
    header = ["順位", "順位変動", "前日順位", "業種名", "前日比率", "前日比率差"]
    lines = [",".join(header)]
    for s in rows:
        cells = [str(s["rank"]), s["move"], str(s["prev_rank"]), s["industry"], s["change_pct"], s["change_pct_diff"]]
        lines.append(",".join('"' + c.replace('"', '""') + '"' for c in cells))
    csv_path.write_text("\n".join(lines), encoding="utf-8")

    time.sleep(1.5)
    print(str(csv_path))
    print(f"業種数: {len(rows)}, 比較対象: {prev_date or 'なし(初回)'}, as_of: {as_of or '不明'}", file=sys.stderr)


if __name__ == "__main__":
    main()


