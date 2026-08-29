"""РосФрукт — две разные страницы одного сайта, две разные роли.

`rosfrukt.ru/product` — не каталог, а фотогалерея-витрина: шесть карточек
товаров вперемешку (фрукты, яйцо, курица, молоко, напиток, рыба), подпись
под картинкой вида «курица тушка 79р». Это маркетинговый якорь «у нас
дёшево», а не прайс-лист — отсюда и правило №5 задачи: «курица тушка 79 ₽»
против 138 ₽ у Фуд Сити выглядит подозрительно, и причина в том, что тут
**нет заявленной единицы измерения** — за тушку, за кг или за полутушку,
сайт не говорит. Число не приводится к кг догадкой: остаётся как есть в
`title`, а роль в `source` явно помечена как витрина, а не поставка.

`rosfrukt.ru/овощи_оптом/` — уже структурированный каталог (виджет tilda/
uKit «goods», разметка schema.org `Offer`/`itemprop=price`), 16 овощей,
цена вида «от 17 руб.». Единица измерения тоже нигде не указана (ни «/кг»,
ни «/шт») — по логике опта овощей это почти наверняка килограмм, но сайт
этого не пишет, поэтому мы не утверждаем: то же правило, тот же приём —
сырой текст цены остаётся в `title`.

⚠ URL с кириллицей нужно запрашивать в percent-encoding и с завершающим
слэшем — `rosfrukt.ru/овощи_оптом` (без %-кодирования, без слэша) отдаёт
404, а `rosfrukt.ru/%D0.../` — 200. Поймано на живом curl 29.08.
"""

from __future__ import annotations

import html as _html
import re
import urllib.parse
import urllib.request

from parsers.snapshot import build_snapshot

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

URL_GALLERY = "https://rosfrukt.ru/product"
URL_VEGETABLES = "https://rosfrukt.ru/" + urllib.parse.quote("овощи_оптом") + "/"

CAPTION = re.compile(
    r'class="caption note"[^>]*>\s*([^<]*?)\s*(\d+(?:[.,]\d+)?)\s*р\.?\s*</div>')


def fetch(url: str) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read().decode("utf-8", "ignore")


def _slug(text: str) -> str:
    clean = re.sub(r"[^\wа-яё ]", " ", text.lower())
    return re.sub(r"\s+", "-", clean).strip("-")[:60]


def parse_gallery(page: str) -> list[dict]:
    """Подписи под фото галереи-витрины: «курица тушка 79р» → товар+цена."""
    items = []
    for name, price_raw in CAPTION.findall(page):
        name = _html.unescape(name).strip()
        if not name:
            continue
        sku = _slug(name)
        if not sku:
            continue
        items.append({
            "sku": sku,
            "shop": "РосФрукт (витрина)",
            "title": f"{name} {price_raw}р (единица не указана сайтом)",
            "price": float(price_raw.replace(",", ".")),
            "currency": "RUB",
            "price_status": "listed",
            "in_stock": True,
        })
    return items


def parse_vegetables(page: str) -> list[dict]:
    """Виджет «goods»: itemprop=name / itemprop=price содержат готовые числа.

    Внимание: первый `itemprop="name"` в разметке этого виджета — служебный
    и пустой (заголовок блока), а не товар. Комбинированный regex «имя ...
    ближайшая цена» на нём один раз ошибочно перепрыгивает через первый
    настоящий товар и склеивает пустое имя с чужой ценой — поймано на живых
    данных (пропадал «картофель»). Поэтому имена, отображаемые цены и числа
    из meta берутся тремя отдельными списками и сшиваются по позиции: пустые
    имена — единственная точка, где список короче остальных, и они просто
    выбрасываются заранее.
    """
    names = [_html.unescape(n).replace("\xa0", " ").strip()
             for n in re.findall(r'itemprop="name"[^>]*>([^<]*)<', page)]
    names = [n for n in names if n]
    displayed = [_html.unescape(p).replace("\xa0", " ").strip()
                for p in re.findall(r'class="price-small[^>]*>([^<]*)</div>', page)]
    raw_prices = re.findall(r'itemprop="price" content="([^"]*)"', page)

    items = []
    for name, price_text, price_content in zip(names, displayed, raw_prices):
        sku = _slug(name)
        if not sku:
            continue
        try:
            price = float(price_content)
        except ValueError:
            price = None
        items.append({
            "sku": sku,
            "shop": "РосФрукт (опт)",
            "title": f"{name.capitalize()} · {price_text} (единица не указана)",
            "price": price,
            "currency": "RUB",
            "price_status": "listed" if price is not None else "unknown",
            "in_stock": price is not None,
        })
    return items


def snapshots() -> list[dict]:
    """Два снимка одного домена — витрина и каталог отвечают на разные вопросы."""
    out = []
    try:
        gallery = parse_gallery(fetch(URL_GALLERY))
        out.append(build_snapshot("РосФрукт · витрина-опт (фотопримеры)", gallery,
                                  status="ok" if gallery else "unreachable"))
    except Exception:
        out.append(build_snapshot("РосФрукт · витрина-опт (фотопримеры)", [],
                                  status="unreachable"))
    try:
        veg = parse_vegetables(fetch(URL_VEGETABLES))
        out.append(build_snapshot("РосФрукт · ОПТ овощи (каталог)", veg,
                                  status="ok" if veg else "unreachable"))
    except Exception:
        out.append(build_snapshot("РосФрукт · ОПТ овощи (каталог)", [],
                                  status="unreachable"))
    return out


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

    pair = snapshots()
    tags = ("rosfrukt-vitrina", "rosfrukt-ovoshi")
    ok_count = 0
    for snap, tag in zip(pair, tags):
        (out / f"{today}-{tag}.json").write_text(
            json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
        ok = snap["source_status"] == "ok"
        ok_count += ok
        print(f"{snap['source']}: {len(snap['items'])} позиций" if ok
              else f"{snap['source']}: источник недоступен")
        for item in list(snap["items"].values())[:5]:
            print(f"  {item['title']}")

    return 0 if ok_count else 1


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv))
