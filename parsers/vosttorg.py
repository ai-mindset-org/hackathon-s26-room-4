"""Восторг — опт-каталог на CS-Cart с ценой, спрятанной в невидимых символах.

`vosttorg.ru/katalog/` — обычная витрина CS-Cart («Каталог продуктов питания
оптом в Москве»), но число цены обёрнуто в `&zwj;` (zero-width joiner,
невидимый символ-соединитель) — `<span>&zwj;250&zwj;</span>`. Это тот же
класс ловушки, что NBSP в примере `parsers/cards.py` (issue #4): наивный
`int()`/`float()` на сыром тексте споткнётся о невидимые символы, которые
никак не показываются в браузере и не видны глазами в HTML-превью. Четырёх-
значные цены сайт почему-то не оборачивает в `&zwj;`, а разбивает `&nbsp;`
(«1&nbsp;750») — то есть один и тот же сайт использует ДВА разных способа
разделения разрядов, и оба ломают наивный парсинг по-разному. Решение одно:
выкинуть из строки все юникод-разделители и оставить только цифры.

Единица продажи указана явно рядом с ценой («за 1 шт.» / «за 1 кг») —
сохраняется в `title`, а не отбрасывается: 250 ₽ за пачку масла 400 г и
250 ₽ за килограмм другого товара — это разные цены, и закупщик должен
видеть разницу с первого взгляда.
"""

from __future__ import annotations

import html as _html
import re
import urllib.request

from parsers.snapshot import build_snapshot

URL = "https://vosttorg.ru/katalog/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# id+название в одной паре: до 8 картинок в начале страницы (слайдер) — с
# пустым alt и без своего product_id, поэтому раздельные списки id/alt едут
# со сдвигом на них. Берём id и alt из ОДНОГО блока товара одним regex'ом.
ID_TITLE = re.compile(
    r'product_data\[(\d+)\]\[product_id\]"\s+value="\d+"\s*/>.*?'
    r'class="ty-pict[^"]*"\s+alt="([^"]*)"', re.S)
PRICE_LINE = re.compile(
    r'id="sec_[a-z_]*price_(\d+)"\s+class="ty-price-num">([^<]*)<')
UNIT_LINE = re.compile(
    r'id="sec_[a-z_]*price_(\d+)_for_item"\s+class="ty-price-num">\s*([^<]*?)\s*<')


def fetch(url: str = URL) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", "ignore")


def _digits_only(raw: str) -> float | None:
    """«&zwj;250&zwj;» и «1&nbsp;750» — оба варианта убираются одинаково."""
    text = _html.unescape(raw)
    text = "".join(ch for ch in text if ch.isdigit() or ch in ".,")
    text = text.replace(",", ".")
    return float(text) if text else None


def parse(page: str) -> list[dict]:
    prices = dict(PRICE_LINE.findall(page))
    units = dict(UNIT_LINE.findall(page))

    items = []
    for pid, title_raw in ID_TITLE.findall(page):
        if pid not in prices:
            continue
        title = _html.unescape(title_raw).strip()
        price = _digits_only(prices[pid])
        unit = units.get(pid, "").strip()

        items.append({
            "sku": pid,
            "shop": "Восторг",
            "title": f"{title} · {unit}" if unit else title,
            "price": price,
            "currency": "RUB",
            "price_status": "listed" if price is not None else "unknown",
            "in_stock": price is not None,
        })
    return items


def snapshot() -> dict:
    try:
        items = parse(fetch())
    except Exception:
        return build_snapshot("Восторг · каталог поставщика (опт)", [],
                              status="unreachable")
    return build_snapshot("Восторг · каталог поставщика (опт)", items,
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
    (out / f"{date.today().isoformat()}-vosttorg.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    if snap["source_status"] != "ok":
        print("источник недоступен")
        return 1
    print(f"Восторг: {len(snap['items'])} позиций\n")
    for item in list(snap["items"].values())[:10]:
        print(f"  {item['title']:<55} {item['price']:>8} ₽")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
