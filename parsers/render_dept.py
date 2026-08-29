# -*- coding: utf-8 -*-
"""Страница отдела «Мясо · Рыба · Курица» для закупщика — черновик v2.

Не трогает core/render.py (чужой модуль) и не читает контракт диффа: это не
дайджест «что изменилось», а срез «где сегодня дешевле и кому звонить» по
последнему снимку каждого источника. Автономный HTML на выходе — один файл,
инлайн CSS, без CDN, работает офлайн.

Что не так было в старой странице (dept-myaso.html) и что здесь исправлено:

1. Ключи API вместо названия товара («cows: 528 → 460») — здесь везде
   человеческое название и явная единица + валюта.
2. Эталоны (ЕС, Росстат) — это не предложения поставщика, а средние по
   рынку. Раньше их падение цены подсвечивалось зелёным как «выгодная
   сделка» — обман. Здесь они не участвуют в сравнении «где дешевле»,
   только в блоке честности внизу.
3. Не было ответа на «что делать» — здесь сверху одна фраза-вывод, у
   каждого товара телефон/канал заказа, если он есть.

Сопоставление товаров с разными названиями (Fishnet, ВкусВилл) с прайсом
Фуд Сити — через parsers/matching.py (score/match), с одним дополнительным
фильтром: засчитываем совпадение только если оба товара распознаны как один
вид (view) — иначе, как показал прогон на живых данных, в пару к форели
подставляется говядина просто потому, что у обоих товаров не считался отруб.
Фильтр не меняет matching.py, только то, как мы читаем его ответ.

Единицы. Фуд Сити, Москва-розница, Fishnet и Росстат отдают цену уже за
килограмм (см. их докстринги в parsers/). ВкусВилл — цену за упаковку с
весом в названии («150 г», «500 г») — здесь она пересчитывается в ₽/кг,
и на странице показаны оба числа. Эталон ЕС — евро за 100 кг живого веса
туши, к рознице не сводится в принципе, поэтому исключён из сравнения.

Запуск:
    python3 -m parsers.render_dept departments/myaso/data site/dept-myaso-v2.html
"""

from __future__ import annotations

import html as _html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parsers.matching import match

# ── что мы знаем про каждый источник ────────────────────────────────────────
# unit_kg: True — цена уже за кг, False — за упаковку (нормализуем по весу
# в названии), None — источник не участвует в сравнении товаров вообще
# (эталон, другая валюта/база).
FOODCITY = "Фуд Сити · ОПТ поставщиков"
MOSKVA = "Москва · розничная цена (потолок)"
FISHNET = "Fishnet · прайсы поставщиков рыбы"
VKUSVILL = ("ВкусВилл · поставщик (розница) · мясо-птица",
            "ВкусВилл · поставщик (розница) · рыба")

SOURCE_META = {
    FOODCITY: dict(role="опт", actionable=True, unit_kg=True,
                   label="Фуд Сити", note="оптовый рынок"),
    MOSKVA: dict(role="потолок розницы", actionable=False, unit_kg=True,
                 label="Москва · розница", note="не поставщик — верхняя граница цены"),
    FISHNET: dict(role="опт (рыба)", actionable=True, unit_kg=True,
                  label="Fishnet", note="прайсы поставщиков рыбы"),
    VKUSVILL[0]: dict(role="розница-поставщик", actionable=True, unit_kg=False,
                       label="ВкусВилл", note="сайт, заказ онлайн"),
    VKUSVILL[1]: dict(role="розница-поставщик", actionable=True, unit_kg=False,
                       label="ВкусВилл", note="сайт, заказ онлайн"),
    "эталон ЕС · beef (не поставщик)": dict(
        role="эталон", actionable=False, unit_kg=None,
        why="цена туши в евро за 100 кг живого веса по ЕС — ориентир движения рынка, не товар в рознице"),
    "эталон ЕС · pigmeat (не поставщик)": dict(
        role="эталон", actionable=False, unit_kg=None,
        why="цена туши в евро за 100 кг живого веса по ЕС — ориентир движения рынка, не товар в рознице"),
    "эталон ЕС · poultry (не поставщик)": dict(
        role="эталон", actionable=False, unit_kg=None,
        why="цена туши в евро за 100 кг живого веса по ЕС — ориентир движения рынка, не товар в рознице"),
    "эталон Росстат · средняя по РФ (не поставщик)": dict(
        role="эталон", actionable=False, unit_kg=None,
        why="средняя цена по всей России — ориентир рынка, не предложение конкретного поставщика"),
}

WEIGHT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(кг|г|гр)\b", re.IGNORECASE)
PHONE_RE = re.compile(r"\+7[\d\s\-()]{9,}")
OUTLIER_PCT = 60  # экономия выше этого % — предупреждаем сверить фасовку


def load_latest(data_dir: str | Path) -> dict[str, dict]:
    """Один снимок на источник — самый свежий по taken_at."""
    latest: dict[str, dict] = {}
    for p in sorted(Path(data_dir).glob("*.json")):
        try:
            snap = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        src = snap.get("source", "")
        if not src:
            continue
        if src not in latest or snap.get("taken_at", "") > latest[src].get("taken_at", ""):
            latest[src] = snap
    return latest


def _slug(text: str) -> str:
    clean = re.sub(r"[^\wа-яё ]", " ", text.lower())
    return re.sub(r"\s+", "-", clean.strip())[:60].strip("-")


_NAME_CUT_RE = re.compile(r"\s+(Вес упаковки|Доп\. информация|Вид|Продукция|Размерный ряд)\s*:")


def _clean_name(title: str) -> str:
    """Название без технического хвоста прайс-листа («Вес упаковки: 10кг
    Вид: Треска Продукция: ...») — иначе список товаров нечитаем, а два
    разных «Белуга, …» неотличимы друг от друга в свёрнутом виде."""
    return _NAME_CUT_RE.split(title)[0].rstrip(", ").strip()[:70]


def _per_kg(title: str, price: float, unit_kg: bool) -> tuple[float, str]:
    """Цена → (₽/кг, пометка о пересчёте). unit_kg=True — уже за кг."""
    if unit_kg:
        return price, ""
    m = WEIGHT_RE.search(title.replace(",", "."))
    if not m:
        return price, ""  # без веса в названии — развесной товар, уже за кг
    val = float(m.group(1).replace(",", "."))
    grams = val * 1000 if m.group(2).lower() == "кг" else val
    if grams <= 0:
        return price, ""
    per_kg = price / (grams / 1000)
    return per_kg, f'{price:g} ₽ за {m.group(0)}'


def _contact(source: str, item: dict) -> tuple[str, str]:
    """(кому звонить/куда идти, телефон-ссылка или пусто)."""
    if source == FISHNET:
        shop = item.get("shop", "")
        phone_m = PHONE_RE.search(shop)
        phone = phone_m.group(0).strip() if phone_m else ""
        company = shop.split("·")[0].strip() if "·" in shop else shop
        return company or "поставщик Fishnet", phone
    if source == FOODCITY:
        return "Фуд Сити, оптовый рынок", ""
    if source in VKUSVILL:
        return "vkusvill.ru (заказ на сайте)", ""
    return item.get("shop", source), ""


def make_offer(source: str, sku: str, item: dict) -> dict | None:
    meta = SOURCE_META.get(source)
    if not meta or item.get("price") is None or item.get("price_status") != "listed":
        return None
    per_kg, pack_note = _per_kg(item["title"], float(item["price"]), bool(meta["unit_kg"]))
    contact, phone = _contact(source, item)
    return {
        "sku": sku, "source": source, "label": meta["label"], "role": meta["role"],
        "title": item["title"], "price_kg": per_kg, "pack_note": pack_note,
        "contact": contact, "phone": phone, "in_stock": bool(item.get("in_stock", True)),
        "match_note": "",
    }


def build_products(snapshots: dict[str, dict]) -> list[dict]:
    products: dict[str, dict] = {}
    order: list[str] = []

    fc = snapshots.get(FOODCITY)
    mr = snapshots.get(MOSKVA)
    if fc:
        for sku, item in fc["items"].items():
            name = item["title"].split(" · ")[0].strip()
            offer = make_offer(FOODCITY, sku, item)
            p = {"key": sku, "name": name, "offers": [], "ceiling": None,
                 "foodcity_unavailable": offer is None}
            if offer:
                p["offers"].append(offer)
            if mr and sku in mr["items"]:
                mitem = mr["items"][sku]
                if mitem.get("price") is not None and mitem.get("price_status") == "listed":
                    p["ceiling"] = {"price": float(mitem["price"]), "label": SOURCE_META[MOSKVA]["label"]}
            products[sku] = p
            order.append(sku)

    canon_names = [products[k]["name"] for k in order]

    for source in (FISHNET, *VKUSVILL):
        snap = snapshots.get(source)
        if not snap:
            continue
        for sku, item in snap["items"].items():
            offer = make_offer(source, sku, item)
            if not offer:
                continue
            best = None
            if canon_names:
                for r in match(item["title"], canon_names):
                    va, vb = r["a"]["view"], r["b"]["view"]
                    if va and va == vb and r["decision"] != "разные товары":
                        best = r
                        break
            if best:
                key = order[canon_names.index(best["candidate"])]
                if best["decision"] == "на подтверждение":
                    offer["match_note"] = (
                        f'похоже на «{best["candidate"]}» (совпадение {best["score"]:.2f} из 1.0) — '
                        'сверьте вес и фасовку перед звонком')
                products[key]["offers"].append(offer)
            else:
                key = f'standalone-{_slug(item["title"])}'
                if key not in products:
                    display = _clean_name(item["title"])
                    products[key] = {"key": key, "name": display, "offers": [], "ceiling": None,
                                      "foodcity_unavailable": False}
                    order.append(key)
                products[key]["offers"].append(offer)

    result = []
    for key in order:
        p = products[key]
        if not p["offers"]:
            continue
        p["offers"].sort(key=lambda o: o["price_kg"])

        # «Лучшая цена» карточки не имеет права быть нечётким совпадением
        # с ценой, оторванной от реальности — иначе форель за 90 ₽/кг
        # (на самом деле солёные ломтики, «похоже, но не уверены» на 0.62)
        # становится заголовком карточки и рисует несуществующую скидку
        # в 88%. Якорь — уверенное предложение (Фуд Сити/прямой ключ);
        # нечёткое совпадение допускается в «лучшие» только если его цена
        # не более чем в 2.5 раза отличается от якоря в любую сторону —
        # правило заказчика: дешевле не значит тот же товар.
        confident = [o for o in p["offers"] if not o["match_note"]]
        no_confident = not confident
        if confident:
            anchor = min(o["price_kg"] for o in confident)
            eligible = confident + [
                o for o in p["offers"]
                if o["match_note"] and anchor * 0.4 <= o["price_kg"] <= anchor * 2.5]
            best = min(eligible, key=lambda o: o["price_kg"])
            for o in p["offers"]:
                if o["match_note"] and o not in eligible:
                    o["match_note"] += " — цена сильно отличается от опта, в сравнение не взята"
        else:
            # Ни одного уверенного предложения (обычно — Фуд Сити временно
            # нет в наличии): дальше только «похоже, но не уверены».
            # Нельзя рисовать по такой цене зелёный бейдж со скидкой —
            # заказчик не должен принимать нечёткое совпадение за цену.
            best = p["offers"][0]

        ceiling = p["ceiling"]
        pct = None
        if ceiling and ceiling["price"] > 0 and not no_confident:
            pct = round((1 - best["price_kg"] / ceiling["price"]) * 100, 1)
        p["best"] = best
        p["pct"] = pct
        p["no_confident"] = no_confident
        result.append(p)
    return result


def _fmt(v: float) -> str:
    s = f"{v:,.0f}" if float(v) == int(v) else f"{v:,.2f}"
    return s.replace(",", " ")


def _badge(pct: float | None, no_confident: bool = False) -> str:
    if no_confident:
        return '<span class="badge flat">нет уверенной цены — только «похоже»</span>'
    if pct is None:
        return '<span class="badge flat">без ориентира для сравнения</span>'
    if pct > 0.5:
        return f'<span class="badge cheap">−{pct:g}% дешевле розницы Москвы</span>'
    if pct < -0.5:
        return f'<span class="badge pricey">+{-pct:g}% дороже розницы Москвы</span>'
    return '<span class="badge flat">на уровне розницы Москвы</span>'


def _offer_row(o: dict, is_best: bool) -> str:
    price = f'{_fmt(o["price_kg"])} ₽/кг'
    pack = f' <span class="pack">({o["pack_note"]})</span>' if o["pack_note"] else ""
    phone = f' · <a class="tel" href="tel:{_html.escape(o["phone"])}">{_html.escape(o["phone"])}</a>' if o["phone"] else ""
    stock = "" if o["in_stock"] else ' <span class="oos">нет в наличии</span>'
    note = f'<div class="matchnote">⚠ {_html.escape(o["match_note"])}</div>' if o["match_note"] else ""
    cls = "offer best" if is_best else "offer"
    return (f'<div class="{cls}"><div class="offer-top">'
            f'<b>{price}</b>{pack} · {_html.escape(o["label"])} '
            f'<span class="role">({_html.escape(o["role"])})</span>{phone}{stock}</div>'
            f'<div class="offer-title">{_html.escape(o["title"])}</div>{note}</div>')


def render_product(p: dict) -> str:
    best, pct = p["best"], p["pct"]
    n_offers = len(p["offers"])
    caution = ""
    if pct is not None and pct >= OUTLIER_PCT:
        caution = ('<div class="caution">⚠ разрыв необычно большой — прежде чем звонить, '
                    'сверьте калибр и фасовку (правило заказчика: дешевле не значит то же самое)</div>')
    if p.get("foodcity_unavailable"):
        caution += ('<div class="caution">⚠ у Фуд Сити эта позиция сейчас «временно нет в наличии» — '
                    'ниже только нечёткие совпадения с других источников</div>')
    ceiling_line = ""
    if p["ceiling"]:
        ceiling_line = (f'<div class="offer ceiling"><div class="offer-top">'
                        f'<b>{_fmt(p["ceiling"]["price"])} ₽/кг</b> · {_html.escape(p["ceiling"]["label"])} '
                        '<span class="role">(потолок, не поставщик)</span></div></div>')
    body = "".join(_offer_row(o, o is best) for o in p["offers"]) + ceiling_line
    more = f'<span class="count">{n_offers} {("предложение" if n_offers == 1 else "предложения" if n_offers < 5 else "предложений")}</span>'
    contact = (f'<a class="tel" href="tel:{_html.escape(best["phone"])}">{_html.escape(best["phone"])}</a>'
               if best["phone"] else _html.escape(best["contact"]))
    return f"""<details class="product">
<summary>
  <span class="name">{_html.escape(p["name"])}</span>
  <span class="price">{_fmt(best["price_kg"])} ₽/кг</span>
  <span class="shop">{_html.escape(best["label"])}</span>
  {_badge(pct, p["no_confident"])}
  <span class="contact">{contact}</span>
  {more}
</summary>
<div class="detail">{caution}{body}</div>
</details>"""


def pick_headline(products: list[dict]) -> dict | None:
    """Самая убедительная и надёжная строка для фразы сверху страницы:
    только прямое сопоставление Фуд Сити ↔ Москва-розница (общий ключ
    источника, а не нечёткое совпадение) — чтобы главное число на странице
    было гарантированно про один и тот же товар."""
    candidates = [p for p in products if p["ceiling"] and p["pct"] is not None
                  and p["pct"] > 0 and any(o["source"] == FOODCITY for o in p["offers"])
                  and p["pct"] < OUTLIER_PCT]
    if not candidates:
        candidates = [p for p in products if p["ceiling"] and p["pct"] is not None and p["pct"] > 0]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p["pct"])


CSS = """
:root{--ink:#181818;--dim:#6f6f6f;--line:#e8e8e8;--bg:#ffffff;
--red:#e11d48;--amber:#d97706;--green:#059669}
*{box-sizing:border-box;margin:0}
body{background:var(--bg);color:var(--ink);
font:16px/1.55 -apple-system,"Segoe UI",Inter,Arial,sans-serif}
.page{max-width:900px;margin:0 auto;padding:28px 24px 80px}
.tag{display:inline-block;font-size:12px;font-weight:700;letter-spacing:.04em;
text-transform:uppercase;color:var(--dim);border:1px solid var(--line);
border-radius:999px;padding:4px 12px;margin-bottom:20px}
.back{display:inline-block;margin-bottom:20px;color:var(--ink);
text-decoration:none;font-weight:600;font-size:15px}
h1{font-weight:800;font-size:clamp(22px,3.4vw,30px);line-height:1.35;
letter-spacing:-.01em;max-width:34ch;margin-bottom:28px}
h1 b{background:linear-gradient(90deg,#f15a24,#ed1e79 60%);
-webkit-background-clip:text;background-clip:text;color:transparent}
h2{font-weight:700;font-size:20px;margin:44px 0 14px;letter-spacing:-.01em}
.sub{color:var(--dim);font-size:14px;margin:-20px 0 28px}
.list{border-top:1px solid var(--line)}
details.product{border-bottom:1px solid var(--line)}
details.product summary{list-style:none;cursor:pointer;padding:13px 4px;
display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
details.product summary::-webkit-details-marker{display:none}
details.product summary::before{content:"›";display:inline-block;width:14px;
color:var(--dim);transition:transform .15s ease;flex:none}
details.product[open] summary::before{transform:rotate(90deg)}
.name{font-weight:600;flex:1 1 200px;min-width:0}
.price{font-weight:800;font-variant-numeric:tabular-nums;white-space:nowrap}
.shop{color:var(--dim);font-size:14px;white-space:nowrap}
.badge{font-size:12.5px;font-weight:700;border-radius:999px;padding:3px 10px;
white-space:nowrap}
.badge.cheap{background:#e7f6ef;color:var(--green)}
.badge.pricey{background:#fdecef;color:var(--red)}
.badge.flat{background:#f2f2f2;color:var(--dim)}
.contact{font-size:13.5px;color:var(--dim);white-space:nowrap}
.count{font-size:12.5px;color:var(--dim);margin-left:auto;white-space:nowrap}
.tel{color:var(--ink);font-weight:600;text-decoration:none;border-bottom:1px solid var(--line)}
.tel:hover{color:var(--green)}
.detail{padding:0 4px 18px 24px}
.offer{padding:9px 0;border-top:1px dashed var(--line)}
.offer:first-child{border-top:none}
.offer-top{font-size:14.5px}
.offer-top b{font-variant-numeric:tabular-nums}
.offer .role{color:var(--dim);font-weight:400;font-size:13px}
.offer-title{color:var(--dim);font-size:13px;margin-top:2px}
.offer.best .offer-top b{color:var(--green)}
.offer.ceiling{opacity:.7}
.pack{color:var(--dim);font-size:13px}
.oos{color:var(--red);font-size:12.5px;font-weight:600}
.matchnote,.caution{font-size:12.5px;color:var(--amber);margin-top:4px;
background:#fff8ec;border-radius:8px;padding:6px 10px}
.honesty{border:1px solid var(--line);border-radius:14px;padding:20px 22px;
margin-top:48px;font-size:14px;color:var(--dim);line-height:1.7}
.honesty b{color:var(--ink)}
.honesty .row{margin-bottom:6px}
footer{border-top:1px solid var(--line);margin-top:32px;padding-top:18px;
color:var(--dim);font-size:12.5px;line-height:1.7}
@media(max-width:520px){.count{display:none}}
"""


def render_html(products: list[dict], snapshots: dict[str, dict], data_dir: str) -> str:
    headline = pick_headline(products)
    if headline:
        h_best, h_pct = headline["best"], headline["pct"]
        hero = (f'Сегодня дешевле всего <b>{_html.escape(headline["name"].lower())}</b> — '
                f'{_fmt(h_best["price_kg"])} ₽/кг у {_html.escape(h_best["label"])}, '
                f'это на {h_pct:g}% ниже потолка розницы Москвы.')
    else:
        hero = "Сегодня нет пары «опт vs розница» для однозначного вывода — смотри список ниже."

    products_sorted = sorted(products, key=lambda p: (p["pct"] is None, -(p["pct"] or -999)))
    rows = "\n".join(render_product(p) for p in products_sorted)

    # В departments/myaso/data параллельно пишут другие отделы (в момент
    # сборки там нашлись каталоги овощей/бакалеи/молочки — чужие снимки,
    # попавшие не в свою папку). Для честного счёта эта страница отдела
    # мяса/рыбы/курицы считает только источники из своей же роли-таблицы,
    # а про случайных соседей говорит отдельной строкой, а не молчит.
    dept_snapshots = {s: v for s, v in snapshots.items() if s in SOURCE_META}
    foreign = sorted(s for s in snapshots if s not in SOURCE_META)

    ok_sources = [s for s, snap in dept_snapshots.items() if snap.get("source_status") == "ok"]
    silent = [s for s, snap in dept_snapshots.items() if snap.get("source_status") != "ok"]
    actionable_srcs = [s for s in ok_sources if SOURCE_META.get(s, {}).get("actionable")]
    benchmark_srcs = [s for s, m in SOURCE_META.items() if m.get("role") == "эталон" and s in ok_sources]
    n_standalone = sum(1 for p in products if p["key"].startswith("standalone-"))

    silent_html = ""
    if silent:
        silent_html = ('<div class="row">⚠ <b>молчат сегодня:</b> '
                       + ", ".join(_html.escape(SOURCE_META.get(s, {}).get("label", s)) for s in silent)
                       + ' — их позиции не считаются пропавшими, просто не в сегодняшнем срезе.</div>')

    bench_groups: dict[str, set[str]] = {}
    for s in benchmark_srcs:
        why = SOURCE_META[s]["why"]
        bench_groups.setdefault(why, set()).add(s.split(" · ")[0])
    bench_why = "; ".join(
        f'{_html.escape(", ".join(sorted(names)))} — {_html.escape(why)}'
        for why, names in bench_groups.items())

    foreign_html = ""
    if foreign:
        foreign_html = (f'<div class="row">ℹ️ ещё <b>{len(foreign)}</b> файла в этой папке — '
                        'снимки других отделов (овощи/бакалея/молочка), сюда попали по ошибке '
                        'параллельного сбора; эта страница их не считает и не показывает.</div>')

    honesty = f"""<div class="honesty">
<div class="row"><b>{len(ok_sources)} из {len(dept_snapshots)}</b> источников мяса/рыбы/курицы ответили сегодня.</div>
{silent_html}
<div class="row"><b>{len(actionable_srcs)}</b> из них — реальные предложения поставщиков
(Фуд Сити, ВкусВилл, Fishnet); Москва-розница — не поставщик, а верхняя граница цены для сравнения.</div>
<div class="row"><b>{len(benchmark_srcs)}</b> эталона в сравнение цен не идут: {bench_why or "нет данных"}.</div>
{foreign_html}
<div class="row">Товаров без пары для сравнения (только один поставщик на позицию): <b>{n_standalone}</b> —
они всё равно в списке выше, просто без бейджа выгоды.</div>
</div>"""

    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<title>Мясо · Рыба · Курица — где сегодня дешевле</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>{CSS}</style></head><body>
<div class="page">
<a class="back" href="dept-myaso.html">← старая версия страницы</a>
<div class="tag">черновик v2 · закупщику</div>
<h1>{hero}</h1>
<div class="sub">Список ниже — по товару в строке, дешевле всех сверху. Клик по строке — все
предложения по этому товару и кто есть кто.</div>
<h2>Товары</h2>
<div class="list">
{rows}
</div>
{honesty}
<footer>hackathon-s26-room-4 · отдел «Мясо · Рыба · Курица» · снимок на {_html.escape(max((s.get("taken_at","")[:10] for s in snapshots.values()), default="—"))} ·
черновик собран parsers/render_dept.py из {_html.escape(str(data_dir))}, сопоставление товаров — parsers/matching.py</footer>
</div>
</body></html>"""


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    data_dir = argv[1] if len(argv) > 1 else "departments/myaso/data"
    out_path = Path(argv[2] if len(argv) > 2 else "site/dept-myaso-v2.html")

    snapshots = load_latest(data_dir)
    if not snapshots:
        print(f"! нет снимков в {data_dir}", file=sys.stderr)
        return 1
    products = build_products(snapshots)
    html_out = render_html(products, snapshots, data_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html_out, encoding="utf-8")
    known = sum(1 for s in snapshots if s in SOURCE_META)
    foreign = len(snapshots) - known
    extra = f" (+{foreign} чужих файлов в папке, не учтены)" if foreign else ""
    print(f"товаров: {len(products)} · источников отдела: {known}{extra} → {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
