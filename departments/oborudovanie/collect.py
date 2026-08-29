#!/usr/bin/env python3
"""PQQM: КленМаркет -> снимок цен в контракте v2.

Использование:
  python3 departments/oborudovanie/collect.py
  python3 departments/oborudovanie/collect.py --out-dir /tmp/snapshots

Каталог отделён от кода: новые позиции добавляются в catalog.json.
Неуспешный запрос не подменяется пустой ценой: создаётся снимок со статусом
source_status=unreachable.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
PRICE_RE = re.compile(
    r'<span[^>]*class="price__current-value"[^>]*itemprop="price"[^>]*content="([0-9]+)"'
)
IN_STOCK_RE = re.compile(r'itemprop="availability"[^>]*InStock', re.IGNORECASE)


def fetch_html(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (PQQM price monitor)"})
    with urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_klenmarket(html, item, shop):
    match = PRICE_RE.search(html)
    if not match:
        return {
            "shop": shop,
            "title": item["title"],
            "price": None,
            "currency": "RUB",
            "price_status": "on_request",
            "in_stock": False,
        }
    return {
        "shop": shop,
        "title": item["title"],
        "price": float(match.group(1)),
        "currency": "RUB",
        "price_status": "listed",
        "in_stock": bool(IN_STOCK_RE.search(html)),
    }


def collect_source(source_config, taken_at):
    snapshot = {
        "taken_at": taken_at,
        "source": source_config["source"],
        "source_status": "ok",
        "items": {},
    }
    try:
        for item in source_config["items"]:
            if source_config["adapter"] != "klenmarket":
                raise ValueError(f'неизвестный адаптер: {source_config["adapter"]}')
            html = fetch_html(item["url"])
            snapshot["items"][item["sku"]] = parse_klenmarket(
                html, item, source_config["shop"]
            )
    except Exception as error:
        snapshot["source_status"] = "unreachable"
        snapshot["items"] = {}
        snapshot["error"] = f"{type(error).__name__}: {error}"
    return snapshot


def format_price(price):
    if price is None:
        return "по запросу"
    return f'{price:,.0f}'.replace(",", " ") + " ₽"


def render_department_page(data_dir, page_path):
    """Показывает последние известные цены, а не только изменения между ними."""
    latest = {}
    for path in sorted(data_dir.glob("*.json")):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if snapshot.get("source_status") != "ok":
            continue
        for sku, item in snapshot.get("items", {}).items():
            latest[(snapshot.get("source", ""), sku)] = (snapshot, item)

    rows = []
    for (source, sku), (snapshot, item) in sorted(latest.items()):
        stock = "в наличии" if item.get("in_stock") else "под заказ / нет в наличии"
        rows.append(
            "<tr>"
            f"<td><b>{escape(item.get('title', sku))}</b><br><small>{escape(sku)}</small></td>"
            f"<td>{format_price(item.get('price'))}</td>"
            f"<td>{escape(stock)}</td>"
            f"<td>{escape(source)}</td>"
            f"<td>{escape(snapshot.get('taken_at', ''))}</td>"
            "</tr>"
        )

    body = "".join(rows) or "<tr><td colspan=\"5\">Нет успешных снимков.</td></tr>"
    page = f"""<!doctype html>
<meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Оборудование кухни · текущие цены</title>
<style>
body{{font:16px/1.5 Inter,Arial,sans-serif;margin:0;background:#fff8f4;color:#231815}}
main{{max-width:1100px;margin:auto;padding:40px 24px}} h1{{font-size:42px;margin:0 0 8px}}
p{{color:#6a5146}} table{{width:100%;border-collapse:collapse;background:white;margin-top:28px}}
th,td{{padding:15px;text-align:left;border-bottom:1px solid #eaded6;vertical-align:top}}
th{{color:#8a5140;font-size:13px;text-transform:uppercase}} small{{color:#806c62}}
.note{{margin-top:24px;padding:14px 16px;background:#ffe7d8;border-radius:12px}}
</style>
<main><a href=\"../../site/index.html\">← Дашборд кухни</a>
<h1>⚙️ Оборудование кухни</h1>
<p>Последние известные цены из успешных снимков PQQM. Дайджест изменений живёт на общем дашборде.</p>
<table><thead><tr><th>Позиция</th><th>Цена</th><th>Наличие</th><th>Источник</th><th>Снято</th></tr></thead><tbody>{body}</tbody></table>
<div class=\"note\">Страница пересобирается командой <code>python3 collect.py</code>. Недоступный источник не стирает последнюю известную цену.</div>
</main>"""
    page_path.write_text(page, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="PQQM: собрать снимок КленМаркет")
    parser.add_argument("--catalog", type=Path, default=HERE / "catalog.json")
    parser.add_argument("--out-dir", type=Path, default=HERE / "data")
    parser.add_argument("--page", type=Path, default=HERE / "index.html")
    args = parser.parse_args()

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    taken_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for source_config in catalog["sources"]:
        snapshot = collect_source(source_config, taken_at)
        safe_source = re.sub(r"[^a-z0-9]+", "-", snapshot["source"].lower()).strip("-")
        safe_time = taken_at.replace(":", "-").replace("+", "plus")
        path = args.out_dir / f"snapshot-{safe_time}-{safe_source}.json"
        path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(path)
    render_department_page(args.out_dir, args.page)
    print(args.page)


if __name__ == "__main__":
    main()
