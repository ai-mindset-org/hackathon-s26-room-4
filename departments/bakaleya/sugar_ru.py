"""Оптовые цены на сахар с sugar.ru — источник с архивом по датам, то есть
настоящая история, а не два снимка с разницей в двадцать минут.

    python departments/bakaleya/sugar_ru.py 2026-08-26 2026-08-27 2026-08-28

Страница https://sugar.ru/pricesdate/YYYY-MM-DD/ — таблица «Город | Фирма |
1 тонна | 10 тонн (самовывоз) | 65 тонн (вагон) | Комментарий», руб./кг с НДС,
цены подают сами компании (наводка Дениса, 4NNT, issue отдела).
Берём Москву. SKU = фирма × партия. Пустая клетка → позиции нет в снимке
(фирма не подала цену на эту партию в этот день — это не «пропала из выдачи»,
а «не подала», поэтому такие фирмы остаются с price_status unknown).
Стандартная библиотека.
"""
import html
import json
import pathlib
import re
import ssl
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128", "Accept-Language": "ru"}
CTX = ssl.create_default_context()
CITY = "Москва"
LOTS = (("1t", "1 тонна"), ("10t", "10 тонн, самовывоз"), ("65t", "65 тонн, вагон"))
DATA = pathlib.Path(__file__).resolve().parent / "data"


def slug(s):
    table = str.maketrans("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", "abvgdeejzijklmnoprstufhccss'y'eua")
    s = s.lower().translate(table)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:40]


def parse(body):
    """Строки фирм по городам; город приходит в первой ячейке с rowspan."""
    rows, city = [], None
    for tr in re.findall(r"<tr class='nit_calentar_firmprice'.*?</tr>", body, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", c))).strip() for c in cells]
        if len(cells) == 6:
            city, cells = cells[0], cells[1:]
        if len(cells) != 5:
            continue
        firm, p1, p10, p65, comment = cells
        rows.append((city, firm, p1, p10, p65, comment))
    return rows


def to_price(s):
    s = s.replace(",", ".").replace(" ", "")
    return float(s) if re.fullmatch(r"\d+(\.\d+)?", s) else None


def snapshot(date):
    url = f"https://sugar.ru/pricesdate/{date}/"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30, context=CTX) as r:
            body = r.read().decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        return {"taken_at": f"{date}T12:00:00", "source": "sugar.ru", "source_status": "unreachable",
                "note": f"не открылась: {type(e).__name__}", "items": {}}
    rows = [r for r in parse(body) if r[0] == CITY]
    items = {}
    for city, firm, p1, p10, p65, comment in rows:
        for (code, lot), raw in zip(LOTS, (p1, p10, p65)):
            price = to_price(raw)
            if price is None:
                continue
            items[f"sahar-{slug(firm)}-{code}"] = {
                "shop": firm, "title": f"Сахар белый, опт {lot}, {firm}, руб./кг с НДС",
                "price": price, "currency": "RUB", "price_status": "listed", "in_stock": True,
                "url": url, "note": comment[:160] or None,
            }
    status = "ok" if rows else "unreachable"
    note = f"живой парсинг sugar.ru, таблица на {date}, {CITY}: {len(rows)} фирм" if rows else \
        f"страница открылась, но таблица на {date} пуста (цены за день ещё не поданы)"
    return {"taken_at": f"{date}T12:00:00", "source": "sugar.ru", "source_status": status,
            "note": note, "items": items}


if __name__ == "__main__":
    for date in sys.argv[1:]:
        snap = snapshot(date)
        out = DATA / f"snapshot-sugar-ru-{date}T12-00.json"
        out.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"→ {out.name}: {snap['source_status']}, позиций {len(snap['items'])} — {snap['note']}", file=sys.stderr)
