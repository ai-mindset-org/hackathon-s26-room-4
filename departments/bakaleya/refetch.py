"""Ежедневный снимок цен отдела «Бакалея»: перезапрашивает URL позиций из
существующего снимка и пишет новый снимок в контракте v2.

    python departments/bakaleya/refetch.py departments/bakaleya/data/snapshot-metro-cc-2026-08-29T13-30.json

Честность (issue #4): страница не открылась → позиция остаётся с прошлой
ценой? НЕТ — цена null, price_status "unknown"; если не открылась ни одна
страница источника → source_status "unreachable" (это не «пропало»).
Цена берётся только из тела ответа, стратегии по убыванию надёжности:
<meta itemprop="price">, JSON-LD Offer.price, Bitrix PRICE JSON 'VALUE',
первое поле "price" в JSON страницы. Только стандартная библиотека.
"""
import html
import http.cookiejar
import json
import pathlib
import re
import ssl
import sys
import urllib.request
from datetime import datetime

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
      "Accept-Language": "ru"}
CTX = ssl.create_default_context()
# cookie-jar обязателен: online.metro-cc.ru ставит cookie 307-редиректом на себя
OPENER = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
    urllib.request.HTTPSHandler(context=CTX))


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with OPENER.open(req, timeout=30) as r:
        return r.status, r.read().decode("utf-8", "ignore")


def _text(body):
    t = html.unescape(re.sub(r"<[^>]+>", " ", body))
    return re.sub(r"\s+", " ", t)


def extract_price(body):
    """Цена самого товара, не соседних карточек: сначала микроразметка,
    потом видимая «Цена … ₽ Цена за 1 шт» (Bitrix-витрины вроде fishport),
    потом JSON. В Bitrix-JSON первые 'VALUE' часто принадлежат блоку
    «похожие товары» — поэтому он последний."""
    for pat in (r'itemprop="price"[^>]*content="([\d.,]+)"',
                r'"@type"\s*:\s*"Offer"[^}]*?"price"\s*:\s*"?([\d.]+)"?',
                r'data-pw="catalog-price"[^>]*>\s*<span[^>]*>\s*([\d\s\xa0]+)'):
        m = re.search(pat, body, re.S)
        if m:
            val = float(re.sub(r"[\s\xa0]", "", m.group(1)).replace(",", "."))
            if val > 0:
                return val
    m = re.search(r"Цена\s*(?:-->)?\s*([\d\s\xa0]{1,9})\s?₽\s*Цена за 1", _text(body))
    if m:
        val = float(re.sub(r"[\s\xa0]", "", m.group(1)))
        if val > 0:
            return val
    for pat in (r"'VALUE'\s*:\s*'([\d.]+)'", r'"price"\s*:\s*"?([\d.]+)"?'):
        m = re.search(pat, body)
        if m and float(m.group(1)) > 0:
            return float(m.group(1))
    return None


def in_stock(body, previous):
    """Только явный сигнал микроразметки; шаблонные «нет в наличии» в
    подвале страницы — не сигнал. Без сигнала — прошлое значение."""
    m = re.search(r'itemprop="availability"[^>]*content="[^"]*?(InStock|OutOfStock|PreOrder)', body)
    if m:
        return m.group(1) == "InStock"
    if re.search(r"schema\.org/(InStock)", body):
        return True
    if re.search(r"schema\.org/(OutOfStock|SoldOut)", body):
        return False
    return previous


def refetch(prev_path):
    prev = json.loads(pathlib.Path(prev_path).read_text(encoding="utf-8"))
    now = datetime.now().replace(microsecond=0)
    items, fetched_ok = {}, 0
    for sku, it in prev["items"].items():
        new = {k: it[k] for k in ("shop", "title", "currency", "url") if k in it}
        url = it.get("url")
        if not url or it.get("price_status") not in ("listed", None) or "/catalog/" in url and url.rstrip("/").split("/")[-1] in ("myka", "masla-rastitelnye", "makarony-pasta"):
            # позиции без карточки товара (не найдены / по запросу) переносим как есть
            new.update(price=None, price_status=it.get("price_status", "unknown"), in_stock=False)
            items[sku] = new
            continue
        try:
            status, body = fetch(url)
            price = extract_price(body)
            fetched_ok += 1
            if price is None:
                new.update(price=None, price_status="unknown", in_stock=False, note="страница открылась, цена не найдена")
            else:
                new.update(price=price, price_status="listed", in_stock=in_stock(body, it.get("in_stock", True)))
        except Exception as e:  # noqa: BLE001 — сеть, 403, таймаут: фиксируем честно
            new.update(price=None, price_status="unknown", in_stock=False, note=f"не открылась: {type(e).__name__}")
        items[sku] = new
        print(f"  {sku:26} {new.get('price')!s:>8} {new['price_status']:10} {'в наличии' if new['in_stock'] else '—'}", file=sys.stderr)

    priced_urls = [u for u in prev["items"].values() if u.get("url")]
    source_status = "ok" if fetched_ok or not priced_urls else "unreachable"
    snap = {
        "taken_at": now.isoformat(),
        "source": prev["source"],
        "source_status": source_status,
        "note": f"живой парсинг {now:%d.%m %H:%M}, refetch.py по URL снимка {pathlib.Path(prev_path).name}",
        "items": items,
    }
    slug = re.sub(r"^snapshot-(.+?)-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}\.json$", r"\1", pathlib.Path(prev_path).name)
    out = pathlib.Path(prev_path).parent / f"snapshot-{slug}-{now:%Y-%m-%dT%H-%M}.json"
    out.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {out}  ({source_status}, страниц открыто {fetched_ok})", file=sys.stderr)
    return out


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, file=sys.stderr)
        refetch(p)
