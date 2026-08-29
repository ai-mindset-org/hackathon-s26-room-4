"""Фуд Сити — оптовые цены поставщиков против розницы Москвы.

Это то, чего не давал ни один прежний источник. Росстат и Еврокомиссия дают
средние по рынку, ВкусВилл — розницу сети. Здесь **оптовая цена, по которой
закупщик реально берёт**, и рядом, в той же строке, розничная цена по Москве.

Страница `dm.foodcity.ru/price-comparison` — таблица из 220 строк:

    Продукт | Наша цена | Цена в магазинах Москвы | Цена за ящик | Кросс-док

Фуд Сити — арендодатель, а не продавец: на прямой вопрос о прайс-листе они
отвечают, что прайса нет, потому что цену ставит каждый поставщик сам. Эта
таблица — сводка диапазонов по павильонам, то есть ближайшее к оптовой цене,
что вообще публикуется.

Отсюда три особенности, которые нельзя игнорировать:

1. **Цена — диапазон, а не число.** «138 - 200 руб.», «от 660 руб.».
   Берём нижнюю границу как цену и сохраняем весь диапазон в названии:
   закупщик ориентируется на «от», а размах важен ему глазами.
2. **Две цены в одной строке.** Оптовая и розничная — это два РАЗНЫХ
   источника, а не два поля. Разводим их в два снимка, тогда модуль
   сравнения магазинов сам покажет разрыв опт/розница.
3. **«Временно нет в наличии»** встречается прямо в колонке цены —
   это `price_status: unknown` и `in_stock: false`, а не ноль.
"""

from __future__ import annotations

import html as _html
import re
import urllib.request

from parsers.snapshot import build_snapshot

URL = "https://dm.foodcity.ru/price-comparison"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# Строки-заголовки категорий внутри таблицы — не товары.
CATEGORIES = ("рыба и морепродукты", "мясо", "овощи", "фрукты", "зелень",
              "ягоды", "грибы", "молочные продукты", "полуфабрикаты",
              "бакалея", "соленья", "алкогольные и безалкогольные напитки")

MEAT_FISH = ("рыба", "мясо", "птиц", "морепродукт")


def fetch(url: str = URL) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", "ignore")


def _cells(row_html: str) -> list[str]:
    out = []
    for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row_html, re.S):
        text = _html.unescape(re.sub(r"<[^>]+>", " ", cell))
        out.append(" ".join(text.replace("\xa0", " ").split()))
    return [c for c in out if c]


def parse_price(raw: str) -> tuple[float | None, str]:
    """«138 - 200 руб.» → (138.0, 'листинг'); «Временно нет» → (None, ...)."""
    text = (raw or "").lower()
    if "нет в наличии" in text or "нет " == text[:4]:
        return None, "unknown"
    numbers = [float(n.replace(",", ".")) for n in
               re.findall(r"\d+(?:[.,]\d+)?", text.replace(" ", ""))]
    if not numbers:
        return None, "unknown"
    return min(numbers), "listed"


def rows(page: str) -> list[list[str]]:
    return [c for c in (_cells(r) for r in
                        re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S)) if c]


def snapshots(page: str | None = None,
              only: tuple[str, ...] = MEAT_FISH) -> list[dict]:
    """Два снимка: оптовый Фуд Сити и розница Москвы — как разные источники."""
    page = page if page is not None else fetch()
    wholesale, retail = [], []
    category = ""

    for cells in rows(page):
        head = cells[0].lower().strip()
        if len(cells) == 1 and head in CATEGORIES:
            category = head
            continue
        if len(cells) < 3 or head in ("продукт",):
            continue
        if only and not any(k in category for k in only):
            continue

        name = cells[0]
        sku = re.sub(r"\s+", "-", re.sub(r"[^\wа-яё ]", " ", name.lower()))[:60]
        sku = sku.strip("-")
        if not sku:
            continue

        opt_price, opt_status = parse_price(cells[1])
        rtl_price, rtl_status = parse_price(cells[2])
        where = cells[4] if len(cells) > 4 else ""

        wholesale.append({
            "sku": sku, "shop": "Фуд Сити (опт)",
            "title": f"{name} · {cells[1]}" + (f" · {where}" if where else ""),
            "price": opt_price, "currency": "RUB",
            "price_status": opt_status,
            "item_status": "ok" if opt_price is not None else "not_found",
            "in_stock": opt_price is not None,
        })
        retail.append({
            "sku": sku, "shop": "розница Москвы",
            "title": f"{name} · {cells[2]}",
            "price": rtl_price, "currency": "RUB",
            "price_status": rtl_status,
            "item_status": "ok" if rtl_price is not None else "not_found",
            "in_stock": rtl_price is not None,
        })

    return [
        build_snapshot("Фуд Сити · ОПТ поставщиков", wholesale,
                       status="ok" if wholesale else "unreachable"),
        build_snapshot("Москва · розничная цена (потолок)", retail,
                       status="ok" if retail else "unreachable"),
    ]


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
    today = date.today().isoformat()

    try:
        pair = snapshots()
    except Exception as exc:
        print(f"источник недоступен: {type(exc).__name__}", file=sys.stderr)
        return 1

    for snap, tag in zip(pair, ("foodcity-opt", "moskva-roznica")):
        (out / f"{today}-{tag}.json").write_text(
            json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    opt, rtl = pair
    print(f"Фуд Сити: {len(opt['items'])} позиций мяса, птицы и рыбы\n")
    print(f"  {'товар':<26} {'опт':>10} {'розница':>10}   выгода")
    for sku, item in list(opt["items"].items())[:14]:
        r = rtl["items"].get(sku, {}).get("price")
        o = item["price"]
        gain = f"{(1 - o / r) * 100:5.0f}%" if o and r and r else "    —"
        name = item["title"].split(" · ")[0]
        print(f"  {name[:26]:<26} {o or '—':>10} {r or '—':>10}   {gain}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
