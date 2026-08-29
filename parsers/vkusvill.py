"""ВкусВилл — российские цены ПО ПОЗИЦИЯМ, а не средние по рынку.

Зачем понадобился. Первый заход в отдел мяса дал Росстат и Еврокомиссию —
это средние по рынку, они отвечают на вопрос «куда пошёл рынок», но не на
вопрос закупщика «почём конкретный товар». Подмена цели была названа вслух
и здесь исправляется: это первый российский источник, где цена привязана к
конкретной позиции.

Цены лежат в JSON-LD (`application/ld+json`, `@type: Product`) прямо в HTML —
ни ключа, ни JS-рендера не нужно. Проверено 29.08 на категориях мяса/птицы
и рыбы: 24 позиции с ценой на одной странице.

⚠ Граница, которую нельзя замалчивать: это РОЗНИЧНАЯ цена сети, а не прайс
оптового поставщика. Закупщику она годится как ориентир и как верхняя
граница («дороже розницы брать точно не надо»), но переговорной ценой
поставщика не является. Оптовые цены в вебе не публикуются вообще — это
свойство рынка, а не пробел в парсере.
"""

from __future__ import annotations

import html as _html
import json
import re
import urllib.request

from parsers.snapshot import build_snapshot

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

CATEGORIES = {
    "мясо-птица": "https://vkusvill.ru/goods/myaso-ptitsa/",
    "рыба": "https://vkusvill.ru/goods/ryba-ikra-i-moreprodukty/",
}


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", "ignore")


def _products(page: str) -> list[dict]:
    """Все Product из ld+json. Блоков несколько, часть — не каталог."""
    found: list[dict] = []
    for block in re.findall(
            r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        nodes = data.get("@graph") if isinstance(data, dict) else data
        if isinstance(data, dict) and not nodes:
            nodes = [data]
        for node in nodes if isinstance(nodes, list) else []:
            if isinstance(node, dict) and node.get("@type") == "Product":
                found.append(node)
    return found


def _sku(name: str) -> str:
    clean = re.sub(r"[^\wа-яё ]", " ", name.lower())
    return re.sub(r"\s+", "-", clean.strip())[:60].strip("-")


def snapshot(category: str = "мясо-птица") -> dict:
    url = CATEGORIES.get(category, category)
    try:
        page = fetch(url)
    except Exception as exc:
        return build_snapshot(f"ВкусВилл · розница · {category}", [],
                              status="unreachable")

    items = []
    for node in _products(page):
        name = _html.unescape(node.get("name", "")).replace("\xa0", " ").strip()
        offer = node.get("offers") or {}
        offer = offer[0] if isinstance(offer, list) and offer else offer
        raw = offer.get("price") if isinstance(offer, dict) else None
        try:
            price = float(str(raw).replace(",", ".")) if raw is not None else None
        except ValueError:
            price = None
        availability = str(offer.get("availability", "")) if isinstance(offer, dict) else ""
        if not name:
            continue
        items.append({
            "sku": _sku(name),
            "shop": "vkusvill.ru",
            "title": name,
            "price": price,
            "currency": (offer.get("priceCurrency") if isinstance(offer, dict)
                         else None) or "RUB",
            "price_status": "listed" if price is not None else "unknown",
            "item_status": "ok" if price is not None else "not_found",
            "in_stock": "OutOfStock" not in availability,
        })

    status = "ok" if items else "unreachable"
    return build_snapshot(f"ВкусВилл · розница · {category}", items, status=status)


def main(argv: list[str]) -> int:
    import sys
    from pathlib import Path
    from datetime import date

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    out = Path(argv[1] if len(argv) > 1 else "departments/myaso/data")
    out.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()

    for category in (argv[2:] or list(CATEGORIES)):
        snap = snapshot(category)
        (out / f"{today}-vkusvill-{category}.json").write_text(
            json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
        if snap["source_status"] != "ok":
            print(f"  {category:<14} источник недоступен")
            continue
        print(f"  {category:<14} позиций {len(snap['items'])}")
        for item in list(snap["items"].values())[:5]:
            print(f"      {item['title'][:42]:<42} {item['price']:>7,.0f} ₽")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
