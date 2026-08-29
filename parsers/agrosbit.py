"""АгроСбыт — доска объявлений «купить/продать оптом», а не витрина магазина.

`agrosbit.ru/vegetables/vegetables` — это не каталог одного продавца, а лента
объявлений РАЗНЫХ поставщиков: у каждой карточки свой продавец, свой телефон,
свои условия (минимальная партия, фасовка, наличный/безнал). Каждая карточка
размечена `schema.org/Product` + `schema.org/Offer`, поэтому имя, цена, валюта
и единица измерения читаются напрямую из атрибутов, без угадывания по тексту.

Объявления бывают двух типов — «Продам» и «Куплю». «Куплю» — это заявка
покупателя, у неё нет цены поставки, её ни в коем случае нельзя показывать
как предложение купить товар. Берём только «Продам» (на живом прогоне 29.08
все 30 карточек первой страницы и были «Продам», но фильтр в коде остаётся
жёстким на будущее).

⚠ Единица измерения указана явно (`/ кг.` или `/ т.`) — и это ловушка похуже
отсутствующей: цена «Огурец Саунд F1 — 45,00 / т.» из этой же выдачи означает
45 РУБЛЕЙ ЗА ТОННУ, то есть 4.5 копейки за килограмм — это либо опечатка
продавца, либо цена за что-то другое (метизы измерения тонна vs кг перепутаны
на самой площадке). Мы не чиним чужую опечатку и не пересчитываем в кг —
единица остаётся в `title` ровно такой, какую написал продавец.

SKU строится из последнего сегмента `itemprop="url"` (у каждого объявления
своя страница на agrosbit.ru) — не из названия товара, потому что несколько
разных продавцов держат объявления с одинаковым названием («Картофель
оптом»), и схлопывать их в один SKU значило бы молча терять предложения
конкурирующих поставщиков — ровно то сравнение цен, ради которого источник
подключается.
"""

from __future__ import annotations

import html as _html
import re
import urllib.request

from parsers.snapshot import build_snapshot

URL = "https://agrosbit.ru/vegetables/vegetables"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

PHONE = re.compile(r"(?:\+7|8)[\s_(]?\d{3}[\s_)]?\d{3}[\s_-]?\d{2}[\s_-]?\d{2}")

CARD = re.compile(
    r'itemprop="url"\s+title="[^"]*"\s+href="([^"]+)".*?'
    r'itemprop="category">([^<]*)</span>.*?'
    r'itemprop="name">([^<]*)</span>.*?'
    r'itemprop="description" content="([^"]*)".*?'
    r'itemprop="price" content="([^"]*)".*?'
    r'lot-price-unit[^>]*>\s*/\s*([^<]+)<.*?'
    r'<span>(Продам|Куплю)</span>',
    re.S)


def fetch(url: str = URL) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", "ignore")


def parse(page: str) -> list[dict]:
    items = []
    for url, category, name, descr, price_raw, unit, offer_type in CARD.findall(page):
        if offer_type != "Продам":
            continue
        name = _html.unescape(name).strip()
        descr = _html.unescape(descr).strip()
        unit = _html.unescape(unit).strip()
        try:
            price = float(price_raw.replace(",", "."))
        except ValueError:
            continue

        phone_match = PHONE.search(descr)
        phone = phone_match.group(0) if phone_match else ""
        sku = url.rstrip("/").rsplit("/", 1)[-1] or _re_slug(name)

        items.append({
            "sku": sku,
            "shop": f"АгроСбыт: продавец{' ' + phone if phone else ' (см. объявление)'}",
            "title": f"{name} · {price_raw.replace('.', ',')} ₽ / {unit}",
            "price": price,
            "currency": "RUB",
            "price_status": "listed",
            "in_stock": True,
            "category": category.strip(),
        })
    return items


def _re_slug(text: str) -> str:
    clean = re.sub(r"[^\wа-яё ]", " ", text.lower())
    return re.sub(r"\s+", "-", clean).strip("-")[:60]


def snapshot() -> dict:
    try:
        items = parse(fetch())
    except Exception:
        return build_snapshot("АгроСбыт · объявления поставщиков", [],
                              status="unreachable")
    return build_snapshot("АгроСбыт · объявления поставщиков", items,
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
    (out / f"{date.today().isoformat()}-agrosbit.json").write_text(
        json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")

    if snap["source_status"] != "ok":
        print("источник недоступен")
        return 1
    print(f"АгроСбыт: {len(snap['items'])} объявлений «Продам»\n")
    for item in list(snap["items"].values())[:10]:
        print(f"  {item['title']:<55} {item['shop']}")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
