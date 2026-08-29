"""Alligator Market — карточки SKU с кодом номенклатуры и остатком на складе.

`alligator.market/ru` — B2B-каталог продуктов (Nuxt-приложение), но первая
партия карточек рендерится на сервере прямо в HTML вместе с разметкой
schema.org (`itemprop=name/lowPrice/priceCurrency`) и собственным кодом
товара («3504.116.21679.1») — читается без JS и без обращения к их API.
Остальной каталог подгружается из вклеенного в страницу Nuxt-payload
(`window.__NUXT__ = ...`) — это обфусцированный по именам переменных JS,
а не JSON, доставать из него данные регэкспом ненадёжно (легко склеить не
то поле не с тем товаром). Берём только то, что уже готовыми строками лежит
в HTML: на живом прогоне 29.08 это 9 карточек. Меньше, чем «карточки SKU»
могло бы значить для всего каталога, но каждая цифра в них проверяемая,
а не собранная угадыванием по обфусцированному payload.

Здесь, в отличие от остальных источников комнаты, **единица измерения
указана явно и по-разному для каждого товара** — платформа хранит остаток
как «8,200 кг.» или «96 шт.» рядом с ценой, поэтому title получает готовую
пару (цена + фасовка/масса товара), а не только число.
"""

from __future__ import annotations

import html as _html
import re
import urllib.request

from parsers.snapshot import build_snapshot

URL = "https://alligator.market/ru"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

CARD = re.compile(
    r'itemprop="lowPrice" content="([^"]*)".*?'
    r'ProductItem__code label">\s*([\d.]+)\s*<.*?'
    r'itemprop="name" class="ProductItem__title">\s*([^<]*?)\s*</div>'
    r'(?:.*?in-stock-quantity">\s*([^<]*?)\s*</div>)?',
    re.S)

CURRENCY = {"RUR": "RUB", "RUB": "RUB"}


def fetch(url: str = URL) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", "ignore")


def parse(page: str) -> list[dict]:
    items = []
    for price_raw, code, name_raw, stock_raw in CARD.findall(page):
        name = _html.unescape(name_raw).strip()
        if not name:
            continue
        try:
            price = float(price_raw)
        except ValueError:
            price = None
        stock = _html.unescape(stock_raw or "").strip()

        items.append({
            "sku": code,
            "shop": "Alligator Market",
            "title": f"{name}" + (f" · остаток {stock}" if stock else ""),
            "price": price,
            "currency": "RUB",
            "price_status": "listed" if price is not None else "unknown",
            "in_stock": bool(stock) and not stock.lower().startswith("0"),
        })
    return items


def snapshot() -> dict:
    try:
        items = parse(fetch())
    except Exception:
        return build_snapshot("Alligator Market · карточки SKU (опт)", [],
                              status="unreachable")
    return build_snapshot("Alligator Market · карточки SKU (опт)", items,
                          status="ok" if items else "unreachable")


def main(argv: list[str]) -> int:
    import json
    import sys
    from datetime import date
    from pathlib import Path

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    out = Path(argv[1] if len(argv) > 1 else "departments/myaso/data")
    out.mkdir(parents=True, exist_ok=True)
    snap = snapshot()
    (out / f"{date.today().isoformat()}-alligator.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    if snap["source_status"] != "ok":
        print("источник недоступен")
        return 1
    print(f"Alligator Market: {len(snap['items'])} карточек SKU "
          f"(только серверный рендер, без Nuxt-payload)\n")
    for sku, item in snap["items"].items():
        print(f"  {sku:<20} {item['title']:<45} {item['price']:>8} ₽")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
