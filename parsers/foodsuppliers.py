"""FoodSuppliers — справочник поставщиков, а не витрина одного магазина.

`foodsuppliers.ru/products` — заглавие страницы прямо говорит, что это:
«Продукты питания оптом — 1437 товаров от 131 поставщика». Одна страница
устроена как список КОМПАНИЙ, и у каждой компании — один или несколько
товаров с ценой прямо внутри её блока (у части компаний товар один, у
некоторых — два-три). Поэтому парсинг идёт в два шага: сначала страница
режется на блоки по компаниям (`content-list-item enterprise-teaser`),
потом внутри каждого блока читаются его собственные товары — иначе, если
искать товар и компанию раздельными списками по всей странице, компания с
двумя товарами и следующая за ней компания с одним съедут по индексам и
результат спутает поставщиков (эта ошибка уже поймана и исправлена в
`parsers/vosttorg.py` на другом сайте — правило то же: то, что должно
принадлежать одной карточке, читается ОДНИМ regex'ом внутри блока этой
карточки, а не двумя параллельными списками по всему документу).

Цена дана как «от 99.00 руб.» — единица измерения (кг, шт., упаковка) не
указана вообще ни у одной позиции на этой странице. Это оптовый B2B-каталог
(сыр, оболочка для колбас, сушки, вода, мясные полуфабрикаты) — вес фасовки
у таких товаров сильно разный, поэтому цена не приводится ни к чему и
остаётся с исходным текстом «от … руб.» в `title`, а не превращается в
число за килограмм.

SKU берётся из URL карточки товара (`/tovar/<slug>`) — он уникален и
привязан к конкретному предложению конкретного поставщика; так же, как в
`parsers/agrosbit.py`, брать SKU из названия товара нельзя: несколько
поставщиков в этом каталоге держат товары с одинаковым названием
(например, несколько предложений «Масло сливочное»), и одинаковый SKU
скрыл бы часть предложений от сравнения цен.
"""

from __future__ import annotations

import html as _html
import re
import urllib.request

from parsers.snapshot import build_snapshot

URL = "https://foodsuppliers.ru/products"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

COMPANY_SPLIT = re.compile(r'(?=<div\s+class="content-list-item enterprise-teaser)')
COMPANY_NAME = re.compile(r'title-site--h3">([^<]+)</a>')
PRODUCT = re.compile(
    r'href="(/tovar/[^"]+)"\s+class="title-site--h4">([^<]+)</a>.*?'
    r'content-prod__price">.*?field-item even"\s*>\s*([^<]+?)\s*</div>',
    re.S)
PRICE_NUMBER = re.compile(r'([\d]+(?:[.,]\d+)?)')


def fetch(url: str = URL) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", "ignore")


def parse(page: str) -> list[dict]:
    items = []
    for block in COMPANY_SPLIT.split(page)[1:]:
        company_match = COMPANY_NAME.search(block)
        company = _html.unescape(company_match.group(1)).strip() \
            if company_match else "поставщик FoodSuppliers"

        for url, name_raw, price_text_raw in PRODUCT.findall(block):
            name = _html.unescape(name_raw).strip()
            price_text = _html.unescape(price_text_raw).strip()
            if "по запросу" in price_text.lower() or "договорн" in price_text.lower():
                price, status = None, "on_request"
            else:
                number = PRICE_NUMBER.search(price_text.replace(",", "."))
                price = float(number.group(1)) if number else None
                status = "listed" if price is not None else "unknown"

            sku = url.rstrip("/").rsplit("/", 1)[-1]
            items.append({
                "sku": sku,
                "shop": company,
                "title": f"{name} · {price_text}",
                "price": price,
                "currency": "RUB",
                "price_status": status,
                "in_stock": price is not None,
            })
    return items


def snapshot() -> dict:
    try:
        items = parse(fetch())
    except Exception:
        return build_snapshot("ФудСаплайерс · каталог объявлений поставщиков", [],
                              status="unreachable")
    return build_snapshot("ФудСаплайерс · каталог объявлений поставщиков", items,
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
    (out / f"{date.today().isoformat()}-foodsuppliers.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    if snap["source_status"] != "ok":
        print("источник недоступен")
        return 1
    print(f"FoodSuppliers: {len(snap['items'])} позиций (страница 1 из 131 "
          f"поставщиков)\n")
    for item in list(snap["items"].values())[:10]:
        print(f"  {item['title']:<55} {item['shop']}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
