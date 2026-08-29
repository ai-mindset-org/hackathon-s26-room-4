"""Страница-справочник: что закупщик видит вместо динамики.

Дайджест отвечает на «что изменилось со вчера» и требует двух снимков. У
большинства поставщиков снимок пока один — и они на дайджест-странице просто
не появляются. Отсюда впечатление, что источников нет, хотя их тринадцать.

Эта страница отвечает на другой вопрос, тот, что закупщик задаёт утром:
**что я покупаю, у кого сегодня дешевле и кому звонить.** Ей хватает одного дня.
"""

from __future__ import annotations

import glob
import html as _html
import json
from pathlib import Path

from parsers.catalog import build_per_kg, is_benchmark
from parsers.matching import score
from parsers.review_queue import build_queue

CSS = """
:root{--ink:#181818;--dim:#6f6f6f;--line:#e8e8e8;--bg:#fff;--card:#fff;
--red:#e11d48;--amber:#b45309;--ok:#047857;--accent:#4f46e5}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1000px;margin:0 auto;padding:40px 24px 80px}
a{color:var(--accent)}
h1{font-size:34px;line-height:1.15;margin:0 0 8px;letter-spacing:-.02em}
.sub{color:var(--dim);margin:0 0 32px}
.lead{font-size:19px;line-height:1.45;margin:0 0 32px;padding:20px 24px;
border:1px solid var(--line);border-radius:12px;background:#fafafa}
.lead b{font-weight:600}
h2{font-size:13px;letter-spacing:.09em;text-transform:uppercase;color:var(--dim);
margin:40px 0 12px;font-weight:600}
table{width:100%;border-collapse:collapse}
td,th{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;
vertical-align:top}
th{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--dim);
font-weight:600}
.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.good{color:var(--ok);font-weight:600}
.bad{color:var(--red)}
.muted{color:var(--dim)}
.pill{display:inline-block;padding:2px 8px;border-radius:99px;font-size:12px;
border:1px solid var(--line);color:var(--dim);white-space:nowrap}
.pill.sup{border-color:#a7f3d0;color:var(--ok);background:#ecfdf5}
.pill.bench{border-color:#e5e7eb;color:var(--dim);background:#f9fafb}
details{border:1px solid var(--line);border-radius:10px;margin-bottom:8px;
background:var(--card)}
summary{padding:14px 16px;cursor:pointer;display:flex;gap:16px;align-items:baseline;
flex-wrap:wrap}
summary::-webkit-details-marker{display:none}
summary .t{font-weight:600;flex:1;min-width:220px}
details[open] summary{border-bottom:1px solid var(--line)}
.inner{padding:4px 16px 12px}
.note{border-left:3px solid var(--amber);padding:12px 16px;background:#fffbeb;
border-radius:0 8px 8px 0;margin:8px 0;color:#78350f}
.foot{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);
color:var(--dim);font-size:13px}
"""


def _esc(text) -> str:
    return _html.escape(str(text or ""))


def _money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def load(folder: str) -> list[dict]:
    return [json.loads(Path(p).read_text(encoding="utf-8"))
            for p in sorted(glob.glob(f"{folder}/*.json"))]


def nomenclature(path: str) -> list[dict]:
    file = Path(path)
    if not file.exists():
        return []
    return json.loads(file.read_text(encoding="utf-8")).get("items", [])


def _offers_for(name: str, snapshots: list[dict], limit: int = 4) -> list[dict]:
    """Предложения под позицию заказчика. Эталоны исключены: они не продают."""
    found = []
    for snap in snapshots:
        if snap.get("source_status") != "ok" or is_benchmark(snap.get("source", "")):
            continue
        for item in snap.get("items", {}).values():
            if item.get("price_status") != "listed" or item.get("price") is None:
                continue
            value = score(name, item.get("title", ""))["score"]
            if value >= 0.6:
                found.append({"score": round(value, 2),
                              "title": item.get("title", ""),
                              "price": float(item["price"]),
                              "shop": item.get("shop") or snap["source"],
                              "source": snap["source"]})
    found.sort(key=lambda o: (-o["score"], o["price"]))
    return found[:limit]


def render(dept_dir="departments/myaso/data",
           nom_path="departments/myaso/nomenclature.json") -> str:
    snaps = load(dept_dir)
    data = build_per_kg(snaps)
    queue = build_queue(snaps)
    wanted = nomenclature(nom_path)

    suppliers = sorted({s["source"] for s in snaps
                        if s.get("source_status") == "ok"
                        and not is_benchmark(s["source"])})
    benches = sorted({s["source"] for s in snaps
                      if s.get("source_status") == "ok"
                      and is_benchmark(s["source"])})

    out = [f"<!doctype html><html lang=ru><meta charset=utf-8>",
           "<meta name=viewport content='width=device-width,initial-scale=1'>",
           "<title>Справочник закупки · Мясо · Рыба · Курица</title>",
           f"<style>{CSS}</style><div class=wrap>",
           "<p><a href='./index.html'>← Кухня</a></p>",
           "<h1>Справочник закупки</h1>",
           f"<p class=sub>Мясо · Рыба · Курица · отдел 4NNT · "
           f"{len(suppliers)} поставщиков, {len(benches)} справочных источника</p>"]

    # ── вывод одной фразой ──
    best_row = next((r for r in data["rows"] if len(r["offers"]) >= 2), None)
    if best_row and best_row["best"]:
        b = best_row["best"]
        out.append(
            f"<p class=lead>Сегодня <b>{_esc(best_row['title'])}</b> дешевле всего "
            f"у <b>{_esc(b['shop'])}</b> — <b>{_money(b['price'])} ₽/кг</b>. "
            f"Это на <b>{best_row['spread_percent']:.0f}%</b> ниже самого дорогого "
            f"предложения из {len(best_row['offers'])}, что мы видим.</p>")

    # ── номенклатура заказчика ──
    if wanted:
        out.append("<h2>Что закупаем — список заказчика</h2><table>"
                   "<tr><th>Позиция заказчика</th><th>Нашлось у поставщиков</th>"
                   "<th class=num>Цена</th></tr>")
        for want in wanted:
            name = want["customer_name"]
            offers = _offers_for(name, snaps, limit=2)
            if not offers:
                out.append(f"<tr><td>{_esc(name)}</td>"
                           f"<td class=muted>не нашлось ни у одного поставщика</td>"
                           f"<td class=num muted>—</td></tr>")
                continue
            first = offers[0]
            out.append(
                f"<tr><td>{_esc(name)}</td><td>{_esc(first['title'][:60])}<br>"
                f"<span class=muted>{_esc(first['shop'][:44])} · совпадение "
                f"{first['score']}</span></td>"
                f"<td class=num>{_money(first['price'])} ₽</td></tr>")
        out.append("</table>")
        out.append("<div class=note>Совпадение ниже 0.85 подтверждает человек — "
                   "автомат не склеивает спорное молча. «Цыплята отборные» на "
                   "уверенности 0.67 подтягивают яйца куриные: цена есть, товар "
                   "не тот.</div>")

    # ── сводка по товарам ──
    rows = [r for r in data["rows"] if len(r["offers"]) >= 2]
    out.append(f"<h2>Один товар у разных поставщиков — {len(rows)} позиций</h2>")
    for row in rows:
        best, worst = row["best"], row["worst"]
        out.append(
            f"<details><summary><span class=t>{_esc(row['title'])}</span>"
            f"<span class='num good'>{_money(best['price'])} ₽/кг</span>"
            f"<span class=muted>{_esc(best['shop'][:34])}</span>"
            f"<span class=pill>разброс {row['spread_percent']:.0f}%</span>"
            f"</summary><div class=inner><table>")
        for offer in row["offers"]:
            delta = ((offer["price"] / best["price"] - 1) * 100
                     if best["price"] else 0)
            mark = "good" if offer is best else ""
            out.append(
                f"<tr><td>{_esc(offer['title'][:64])}</td>"
                f"<td><span class='pill sup'>поставщик</span> "
                f"{_esc(offer['shop'][:40])}</td>"
                f"<td class='num {mark}'>{_money(offer['price'])} ₽/кг</td>"
                f"<td class=num>{'' if delta <= 0 else f'+{delta:.0f}%'}</td></tr>")
        for bench in row["benchmarks"][:2]:
            out.append(
                f"<tr><td class=muted>{_esc(bench['title'][:64])}</td>"
                f"<td><span class='pill bench'>справка</span> "
                f"<span class=muted>{_esc(bench['source'][:40])}</span></td>"
                f"<td class='num muted'>{_money(bench['price'])} ₽/кг</td>"
                f"<td></td></tr>")
        out.append("</table></div></details>")

    # ── источники ──
    out.append("<h2>Откуда берём цены</h2><table>"
               "<tr><th>Источник</th><th>Роль</th></tr>")
    for source in suppliers:
        out.append(f"<tr><td>{_esc(source)}</td>"
                   f"<td><span class='pill sup'>поставщик — можно купить</span></td></tr>")
    for source in benches:
        out.append(f"<tr><td class=muted>{_esc(source)}</td>"
                   f"<td><span class='pill bench'>справка — опорная линия, "
                   f"не продаёт</span></td></tr>")
    out.append("</table>")

    # ── честность ──
    out.append(
        f"<h2>Что требует человека</h2>"
        f"<table><tr><th>Гейт</th><th class=num>Вопросов</th></tr>"
        f"<tr><td>Спорная привязка товара (0.60–0.85)</td>"
        f"<td class=num>{len(queue['gate_match'])}</td></tr>"
        f"<tr><td>Неизвестная единица измерения</td>"
        f"<td class=num>{len(queue['gate_unit'])}</td></tr>"
        f"<tr><td>Роль нового источника</td>"
        f"<td class=num>{len(queue['gate_source'])}</td></tr>"
        f"<tr><td class=muted>Привязано автоматически</td>"
        f"<td class='num muted'>{queue['auto_matched']}</td></tr></table>")

    out.append(
        f"<p class=foot>Источников ответило {data['sources_ok']} из "
        f"{data['sources_total']}. Цены приведены к килограмму там, где в "
        f"названии есть вес; {len(data['not_comparable'])} позиций привести "
        f"нельзя — они не выброшены, но и не сравниваются. "
        f"Справочные источники (ЕС, Росстат, розничный потолок) в подбор "
        f"предложений не идут: они не продают.</p></div></html>")
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    html = render()
    Path("site").mkdir(exist_ok=True)
    Path("site/dept-myaso-catalog.html").write_text(html, encoding="utf-8")
    print(f"страница собрана: site/dept-myaso-catalog.html ({len(html)} байт)")
