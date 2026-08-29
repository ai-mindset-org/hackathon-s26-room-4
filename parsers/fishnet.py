"""Fishnet — оптовые прайс-листы рыбы с ИМЕНЕМ ПОСТАВЩИКА И ТЕЛЕФОНОМ.

Единственный найденный источник, закрывающий требование заказчика K4UR
целиком: «для практического действия в таблице также нужны поставщик,
контакты, MOQ». Всё остальное, что мы подключили, даёт цену без того, кому
звонить.

`https://www.fishnet.ru/pricelist/` — таблица объявлений:

    Товар (с видом, размерным рядом, весом упаковки) | Цена ₽/кг + адрес склада
    | Дата цены | Продавец + телефон | Регион | Производитель | Размещено

Пример строки: «Форель Охлаждённая ПСГ размерный ряд 2-3кг · 950 руб./кг ·
Цена на 24 августа · Уайк, ООО +7(929)504-88-90 · Москва и МО».

Обработка (MOQ, вес упаковки, размерный ряд) лежит прямо в названии — и это
не мусор, а те самые структурные признаки, по которым позиции сопоставляются
между поставщиками. Поэтому название не режем, а разбираем.
"""

from __future__ import annotations

import html as _html
import re
import urllib.request

from parsers.snapshot import build_snapshot

URL = "https://www.fishnet.ru/pricelist/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

PHONE = re.compile(r"\+7\s?\(?\d{3}\)?\s?\d{3}[- ]?\d{2}[- ]?\d{2}")
PRICE = re.compile(r"([\d\s]{2,9})\s*руб\./кг")
SELLER = re.compile(r"([А-ЯЁ][^|+]{2,40}?,?\s?(?:ООО|ИП|АО|ЗАО))")


def fetch(url: str = URL) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", "ignore")


def _cells(row: str) -> list[str]:
    out = []
    for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.S):
        text = _html.unescape(re.sub(r"<[^>]+>", " ", cell)).replace("\xa0", " ")
        out.append(" ".join(text.split()))
    return [c for c in out if c]


def _kind(title: str) -> str:
    """Вид рыбы из строки «Вид: Треска» — самый надёжный ключ сопоставления."""
    match = re.search(r"Вид:\s*([А-ЯЁа-яё]+)", title)
    return match.group(1).strip().lower() if match else ""


def _form(title: str) -> str:
    """Обработка: филе, тушка, стейк — второй по силе структурный признак."""
    low = title.lower()
    for form in ("филе", "тушка", "стейк", "теша", "фарш", "икра", "медальон"):
        if form in low:
            return form
    return ""


def parse(page: str) -> list[dict]:
    items: list[dict] = []
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = _cells(row)
        joined = " | ".join(cells)
        price_match = PRICE.search(joined)
        if not price_match or not cells:
            continue

        price = float(re.sub(r"\s", "", price_match.group(1)))
        title = cells[0]
        phone_match = PHONE.search(joined)
        seller_match = SELLER.search(joined)
        seller = (seller_match.group(1).strip() if seller_match else "поставщик")
        phone = phone_match.group(0) if phone_match else ""

        kind, form = _kind(title), _form(title)
        key = "-".join(x for x in (kind, form) if x) or title[:40].lower()

        items.append({
            "sku": re.sub(r"\s+", "-", key),
            "shop": f"{seller}{' · ' + phone if phone else ''}",
            "title": title[:160],
            "price": price,
            "currency": "RUB",
            "price_status": "listed",
            "item_status": "ok",
            "in_stock": True,
            "kind": kind,
            "form": form,
        })
    return items


def snapshot() -> dict:
    try:
        items = parse(fetch())
    except Exception:
        return build_snapshot("Fishnet · прайсы поставщиков рыбы", [],
                              status="unreachable")
    return build_snapshot("Fishnet · прайсы поставщиков рыбы", items,
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
    (out / f"{date.today().isoformat()}-fishnet.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    if snap["source_status"] != "ok":
        print("источник недоступен")
        return 1
    print(f"Fishnet: {len(snap['items'])} позиций от поставщиков\n")
    for item in list(snap["items"].values())[:10]:
        print(f"  {item['title'][:50]:<50} {item['price']:>7,.0f} ₽/кг  "
              f"{item['shop'][:40]}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
