"""Страница «Классификатор» — то, на чём держится любая цифра о выгоде.

Все остальные страницы показывают ВЫВОД: где дешевле, на сколько, у кого.
Вывод верен ровно настолько, насколько верно сопоставление под ним. Пока
сопоставление не показано, «форель 440 против 780» — это просьба поверить
на слово, а закупщику надо проверить глазами.

Поэтому здесь показывается не результат, а сама склейка:

    строка классификатора  (вид + отруб, транк ТН ВЭД)
      ├ Фуд Сити (опт)   «Рыба Форель (охлажденная) · 440 - 780 руб.»
      │                   440 ₽ за кг       → 440 ₽/кг    совпало 0.91
      └ Уайк ООО         «Форель радужная потр. 1.5 кг»
                          3 825 ₽ за 1.5 кг → 2 550 ₽/кг  собран из признаков

Три вещи, которые страница обязана показать рядом:

1. **Наименование поставщика дословно.** Не наш канон, а его строка — иначе
   проверить нечего: наш канон и есть то, что проверяют.
2. **Цену как опубликована и цену приведённую, с формулой приведения.**
   «3 825 ₽ за 1.5 кг → 2 550 ₽/кг» проверяется в уме за секунду.
3. **Уверенность и то, чем склеено.** 0.67 «собран из признаков» и 0.95
   «совпало» — разные основания, и закупщик имеет право видеть, какое из них
   стоит за строкой, которую ему предлагают как выгоду.

Позиции, которые привести к килограмму нельзя, не прячутся: они внизу, с
причиной. Товар, пропавший молча, читается как «его никто не продаёт».
"""

from __future__ import annotations

import glob
import html as _html
import json
from pathlib import Path

from parsers.catalog import build_per_kg, canon_title, is_benchmark
from parsers.matching import features, score

CSS = """
:root{--ink:#181818;--dim:#6f6f6f;--line:#e8e8e8;--bg:#fff;--card:#fff;
--red:#e11d48;--amber:#b45309;--ok:#047857;--accent:#4f46e5}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
nav{display:flex;justify-content:space-between;align-items:center;
padding:16px 24px;border-bottom:1px solid var(--line);flex-wrap:wrap;gap:8px}
nav .brand{font-family:"Inter Tight",Inter,sans-serif;font-weight:800;
text-decoration:none;color:var(--ink);letter-spacing:-.01em}
nav .links a{color:var(--ink);text-decoration:none;margin-left:22px;font-size:14px}
nav .links a:hover{color:var(--accent)}
.wrap{max-width:1080px;margin:0 auto;padding:36px 24px 80px}
a{color:var(--accent)}
h1{font-size:34px;line-height:1.15;margin:0 0 8px;letter-spacing:-.02em}
h2{font-size:20px;margin:44px 0 12px;letter-spacing:-.01em}
.sub{color:var(--dim);margin:0 0 22px}
.lead{font-size:17px;line-height:1.5;background:#f7f7fb;border:1px solid var(--line);
border-radius:12px;padding:16px 18px;margin:0 0 28px}
table{width:100%;border-collapse:collapse;font-size:14px;margin:6px 0 0}
th{text-align:left;font-weight:600;color:var(--dim);font-size:12px;
text-transform:uppercase;letter-spacing:.04em;padding:6px 8px;
border-bottom:1px solid var(--line)}
td{padding:8px;border-bottom:1px solid var(--line);vertical-align:top}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.muted{color:var(--dim)}
.good{color:var(--ok);font-weight:600}
.warn{color:var(--amber)}
details{border:1px solid var(--line);border-radius:12px;margin:8px 0;
background:var(--card);overflow:hidden}
summary{cursor:pointer;padding:12px 16px;display:flex;gap:12px;align-items:baseline;
flex-wrap:wrap;list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸";color:var(--dim);font-size:12px}
details[open] summary::before{content:"▾"}
summary .t{font-weight:600;flex:1;min-width:200px}
.inner{padding:0 16px 14px;border-top:1px solid var(--line)}
.pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:99px;
border:1px solid var(--line);color:var(--dim);white-space:nowrap}
.pill.sup{border-color:#c7d2fe;color:#4338ca;background:#eef2ff}
.pill.bench{border-color:#e5e7eb;background:#f9fafb}
.pill.tnved{border-color:#fde68a;background:#fffbeb;color:#92400e;
font-variant-numeric:tabular-nums}
.pill.auto{border-color:#a7f3d0;background:#ecfdf5;color:#047857}
.pill.gate{border-color:#fecaca;background:#fef2f2;color:#b91c1c}
.formula{font-size:12.5px;color:var(--dim);font-variant-numeric:tabular-nums}
.raw{font-size:13px}
.note{background:#fffbeb;border:1px solid #fde68a;border-radius:10px;
padding:12px 14px;margin:14px 0;font-size:13.5px;color:#78350f}
.foot{margin-top:56px;padding-top:20px;border-top:1px solid var(--line);
color:var(--dim);font-size:13px}
"""

NAV = ("<nav><a class=brand href='./index.html'>&#127859; КУХНЯ</a>"
       "<span class=links>"
       "<a href='./search.html'>Найти товар</a>"
       "<a href='./dept-myaso-catalog.html'>Справочник закупки</a>"
       "<a href='./classifier.html'>Классификатор</a>"
       "<a href='./digest.html'>Общий дайджест</a></span></nav>")


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


def tnved_for(row: dict, wanted: list[dict]) -> dict | None:
    """Позиция заказчика, к которой относится строка классификатора.

    Сопоставляем тем же матчером, что и товары: если вид у канона и у позиции
    заказчика разный, матчер вернёт 0.0 и никакого ТН ВЭД не подставится —
    ровно то поведение, ради которого вид сделан блокирующим.
    """
    best, value = None, 0.0
    for want in wanted:
        got = score(row["title"], want["customer_name"])["score"]
        if got > value:
            best, value = want, got
    return dict(best, match=round(value, 2)) if best and value >= 0.6 else None


def render(dept_dir="departments/myaso/data",
           nom_path="departments/myaso/nomenclature.json") -> str:
    snaps = load(dept_dir)
    data = build_per_kg(snaps)
    wanted = nomenclature(nom_path)
    rows = data["rows"]

    offers_total = sum(len(r["offers"]) + len(r["benchmarks"]) for r in rows)
    gates = sum(1 for r in rows for o in r["offers"]
                if o.get("decision") == "на подтверждение")

    out = ["<!doctype html><html lang=ru><meta charset=utf-8>",
           "<meta name=viewport content='width=device-width,initial-scale=1'>",
           "<title>Классификатор · как товар склеивается с товаром</title>",
           f"<style>{CSS}</style>", NAV, "<div class=wrap>",
           "<h1>Классификатор</h1>",
           f"<p class=sub>Мясо · Рыба · Курица · отдел 4NNT · "
           f"{len(rows)} строк классификатора, {offers_total} привязанных "
           f"позиций от {data['sources_ok']} источников</p>",
           "<p class=lead>Каждая цифра о выгоде держится на том, что две "
           "строки от разных поставщиков — это один и тот же товар. Здесь "
           "видно саму склейку: <b>наименование поставщика дословно</b>, "
           "<b>его цена как опубликована</b>, <b>чем она приведена к "
           "килограмму</b> и <b>на какой уверенности</b> позиция притянута. "
           "Не сходится глазами — значит, цифра выгоды на предыдущей "
           "странице тоже не сходится.</p>"]

    if gates:
        out.append(f"<div class=note>{gates} позиций притянуты на уверенности "
                   f"0.60–0.85 — они помечены «на подтверждение» и ждут "
                   f"человека. Автомат не склеивает спорное молча.</div>")

    for row in rows:
        want = tnved_for(row, wanted)
        best = row["best"]
        head = [f"<summary><span class=t>{_esc(row['title'])}</span>"]
        if want and want.get("tnved"):
            head.append(f"<span class='pill tnved'>ТН ВЭД {_esc(want['tnved'])}"
                        f"</span>")
        head.append(f"<span class=pill>{len(row['offers'])} поставщик"
                    f"{'ов' if len(row['offers']) != 1 else ''}</span>")
        if best:
            head.append(f"<span class='num good'>{_money(best['price'])} ₽/кг"
                        f"</span>")
        head.append("</summary>")
        out.append("<details>" + "".join(head) + "<div class=inner>")

        if want:
            price = want.get("purchase_price")
            line = (f"Позиция заказчика: <b>{_esc(want['customer_name'])}</b> "
                    f"· совпадение с каноном {want['match']}")
            if want.get("tnved_title"):
                line += f" · {_esc(want['tnved_title'])}"
            if price:
                line += f" · закупают по <b>{_money(price)} ₽/кг</b>"
                if best:
                    delta = (best["price"] / price - 1) * 100
                    word = ("дешевле" if delta < 0 else "дороже")
                    line += (f" — лучшее найденное <b>{word} на "
                             f"{abs(delta):.0f}%</b>")
            else:
                line += " · закупочную цену заказчик не дал"
            out.append(f"<p class=raw>{line}</p>")

        out.append("<table><tr><th>Наименование у поставщика</th>"
                   "<th>Источник</th><th class=num>Как опубликовано</th>"
                   "<th>Приведение</th><th class=num>₽/кг</th>"
                   "<th>Склеено</th></tr>")

        for bucket, kind in (("offers", "sup"), ("benchmarks", "bench")):
            for offer in row[bucket]:
                f = features(offer["title"])
                weight = f["weight"] or "за кг"
                decision = offer.get("decision", "")
                conf = offer.get("confidence", "")
                pill = ("gate" if decision == "на подтверждение"
                        else "auto" if decision == "совпало" else "")
                role = ("поставщик" if kind == "sup" else "справка")
                out.append(
                    f"<tr><td class=raw>{_esc(offer['title'][:78])}</td>"
                    f"<td><span class='pill {kind}'>{role}</span> "
                    f"<span class=muted>{_esc(offer['shop'][:34])}</span></td>"
                    f"<td class='num muted'>{weight}</td>"
                    f"<td class=formula>{_esc(offer.get('basis', '—'))}</td>"
                    f"<td class='num{" good" if offer is best else ""}'>"
                    f"{_money(offer['price'])}</td>"
                    f"<td><span class='pill {pill}'>{_esc(decision)} "
                    f"{conf}</span></td></tr>")
        out.append("</table></div></details>")

    # ── что привести нельзя ──
    bad = data.get("not_comparable", [])
    if bad:
        out.append(f"<h2>Не приводится к килограмму — {len(bad)} позиций</h2>"
                   "<p class=sub>Не выброшены. Товар, пропавший молча, "
                   "читается как «его никто не продаёт».</p>"
                   "<table><tr><th>Позиция</th><th>Источник</th>"
                   "<th>Почему не приводится</th></tr>")
        for item in bad[:40]:
            out.append(f"<tr><td class=raw>{_esc(item['title'][:70])}</td>"
                       f"<td class=muted>{_esc(item['shop'][:32])}</td>"
                       f"<td class=warn>{_esc(item.get('reason', ''))}</td></tr>")
        out.append("</table>")

    # ── что вообще не опознано ──
    unknown = data.get("unknown", [])
    if unknown:
        out.append(f"<h2>Не опознано классификатором — {len(unknown)} позиций"
                   f"</h2><p class=sub>Ни вид, ни отруб не вычитались из "
                   f"названия. Это карта того, что классификатору ещё "
                   f"предстоит выучить.</p><table>"
                   "<tr><th>Позиция</th><th>Источник</th></tr>")
        for item in unknown[:30]:
            out.append(f"<tr><td class=raw>{_esc(item['title'][:70])}</td>"
                       f"<td class=muted>{_esc(item['shop'][:32])}</td></tr>")
        out.append("</table>")

    out.append(
        f"<p class=foot>Источников ответило {data['sources_ok']} из "
        f"{data['sources_total']}. Классификатор — ТН ВЭД на уровне транка "
        f"«вид + термическое состояние»; отруб держится отдельным полем, "
        f"потому что ни один официальный классификатор до отрубов не доходит. "
        f"Вид животного блокирует склейку: разные виды не сходятся ни при "
        f"какой уверенности.</p></div>")
    return "".join(out)


def main() -> int:
    html = render()
    Path("site").mkdir(exist_ok=True)
    Path("site/classifier.html").write_text(html, encoding="utf-8")
    print(f"site/classifier.html — {len(html):,} байт".replace(",", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
