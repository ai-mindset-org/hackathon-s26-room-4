# -*- coding: utf-8 -*-
"""Дашборд кухни: сканирует departments/, собирает site/index.html.

Карточка отдела: владелец, счётчики изменений по последней паре снимков,
доступность источников, ссылка на страницу отдела (если руководитель её
сделал) либо на сгенерированный дайджест отдела.

Запуск: python -m core.kitchen  [--root .] [--site site]
"""

import argparse
import html as _html
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from core import digest as dg
from core import render, theme
from core.build import pairs_from_dir

REPO = "https://github.com/ai-mindset-org/hackathon-s26-room-4"


def dept_summary(dept_dir):
    """-> (pairs, counts, sources_ok, sources_total, last_date, n_items)"""
    data = dept_dir / "data"
    if not data.is_dir():
        return None
    pairs = pairs_from_dir(data)
    if not pairs:
        snaps = [p for p in data.glob("*.json")]
        return {"pairs": [], "n_snaps": len(snaps)}
    d = dg.build_digest(pairs)
    # позиции считаем по последнему снимку КАЖДОГО источника, включая те,
    # у которых пары ещё нет — они под надзором, просто без диффа
    import json as _json
    from core import snapshot as _snap
    latest = {}
    for p_ in sorted(data.glob("*.json")):
        try:
            s_ = _snap.load(p_)
        except (_json.JSONDecodeError, KeyError):
            continue
        key = s_["source"] or p_.parent.name
        if key not in latest or s_["taken_at"] > latest[key]["taken_at"]:
            latest[key] = s_
    n_items = sum(len(s_["items"]) for s_ in latest.values()
                  if s_.get("source_status") == "ok")
    return {"pairs": pairs, "digest": d, "n_items": n_items,
            "n_snaps": len(list(data.glob("*.json")))}


def build_site(root=".", site="site"):
    root, site_dir = pathlib.Path(root), pathlib.Path(root, site)
    site_dir.mkdir(parents=True, exist_ok=True)
    cards, all_pairs = [], []

    for dept_json in sorted(root.glob("departments/*/dept.json")):
        dept_dir = dept_json.parent
        meta = json.loads(dept_json.read_text(encoding="utf-8"))
        s = dept_summary(dept_dir)

        own_page = dept_dir / "index.html"
        href, cls, stat = None, "empty", "ждёт первых снимков"
        if not (s and s.get("pairs")):
            # своих снимков нет — показываем ОБРАЗЕЦ дайджеста, чтобы было
            # видно, что получится (docs/sample-data/<отдел>/)
            sample = root / "docs" / "sample-data" / meta["code"]
            sample_pairs = pairs_from_dir(sample) if sample.is_dir() else []
            if sample_pairs:
                d_smp = dg.build_digest(sample_pairs)
                page = site_dir / f'dept-{meta["code"]}.html'
                page.write_text(render.to_html(
                    d_smp, title=f'{meta["emoji"]} {meta["title"]} — ОБРАЗЕЦ '
                    'дайджеста (замени данными своего отдела)'), encoding="utf-8")
                href, cls = page.name, "empty"
                if s and s.get("n_snaps"):
                    stat = (f'снимков: <b>{s["n_snaps"]}</b> — для сравнения '
                            'нужна пара по одному источнику · '
                            '<u>образец дайджеста ↗</u>')
                else:
                    stat = ("ждёт первых снимков · <u>образец дайджеста ↗</u><br>"
                            f'как класть данные: departments/{meta["code"]}/README.md')
        if s and s.get("pairs"):
            all_pairs.extend(s["pairs"])
            d = s["digest"]
            c = d["counts"]
            stat = (f'позиции: <b>{s["n_items"]}</b> · '
                    f'<b class="red">{c["red"]}</b> красных · '
                    f'<b class="warn">{c["warn"]}</b> жёлтых · '
                    f'<b class="ok">{c.get("deal", 0)}</b> зелёных'
                    f'<br>источники <b class="ok">{d["sources_ok"]}/{d["sources_total"]}</b>'
                    f' · снимки {s["n_snaps"]} · {d["date_from"]} → {d["date_to"]}')
            cls = ""
            page = site_dir / f'dept-{meta["code"]}.html'
            page.write_text(render.to_html(
                d, title=f'{meta["emoji"]} {meta["title"]} · {meta["owner"]}'),
                encoding="utf-8")
            href = page.name
        elif s and s.get("n_snaps") and not href:
            stat = f'снимков: {s["n_snaps"]} — нужен второй для сравнения'
        if own_page.exists():
            # копия в site/ — на деплой уходит только эта папка;
            # ссылку «назад» в копии приводим к корню сайта
            own_copy = site_dir / f'dept-{meta["code"]}-own.html'
            own_copy.write_text(
                own_page.read_text(encoding="utf-8").replace("../../site/", ""),
                encoding="utf-8")
            href = own_copy.name
            cls = ""
            stat += " · своя страница ↗"

        cards.append(
            f'<a class="card {cls}" {"href=" + chr(34) + href + chr(34) if href else ""}>'
            f'<div class="emoji">{meta["emoji"]}</div>'
            f'<div class="title">{_html.escape(meta["title"])}</div>'
            f'<div class="owner">{_html.escape(meta["owner"])}</div>'
            f'<div class="stat-line">{stat}</div></a>')

    cta = (f'<a class="dash-link" href="{REPO}#-живой-дашборд-'
           'httpsroom4-kitchennetlifyapp">как подключить свой отдел</a>')
    d_all = None
    if all_pairs:
        d_all = dg.build_digest(all_pairs)
        (site_dir / "digest.html").write_text(
            render.to_html(d_all, title="Общий дайджест кухни"), encoding="utf-8")
        (site_dir / "digest.md").write_text(dg.to_markdown(d_all), encoding="utf-8")
        try:
            from core.excel import write_xlsx
            write_xlsx(all_pairs, site_dir / "kitchen-digest.xlsx")
            cta = ('<a class="dash-link" href="kitchen-digest.xlsx">'
                   'Excel для закупки ⤓</a> ' + cta)
        except ImportError:
            pass
        cta = ('<a class="pill" href="digest.html">Общий дайджест кухни ↗</a> '
               + cta)

    def stat(label, value, cls=""):
        return (f'<div class="stat"><div class="label">{label}</div>'
                f'<div class="value {cls}">{value}</div></div>')

    live = sum(1 for c_ in cards if 'class="card empty' not in c_)
    n_items_total = sum(len(b["items"]) for _, b, _ in all_pairs)
    agg = d_all["counts"] if d_all else {"red": 0, "warn": 0, "deal": 0}
    src = (f'{d_all["sources_ok"]}/{d_all["sources_total"]}' if d_all else "—")

    stats = ('<div class="stats">'
             + stat("отделов кухни", len(cards))
             + stat("с живыми данными", live, "grad" if live else "")
             + stat("позиций под надзором", n_items_total or "—")
             + stat("источников доступно", src)
             + stat("сигналов сегодня",
                    agg["red"] + agg["warn"] + agg.get("deal", 0))
             + "</div>")

    page = (theme.head("Кухня · комната 4") + theme.CANVAS
            + '<div class="page">'
            '<nav><a class="brand" href="./">🍽 КУХНЯ · комната 4</a>'
            f'<span class="links"><a href="{REPO}">Репозиторий</a>'
            '<a href="digest.html">Дайджест</a></span></nav>'
            '<h1>Кухня следит за ценами, пока закупщики готовят.</h1>'
            '<div class="lede">Пять отделов ресторана мониторят закупочные '
            'цены каждый по-своему — инструмент собирает снимки, сравнивает '
            'с историей и честно говорит, что подорожало, что подешевело '
            'и куда сегодня не удалось посмотреть. Заказчик: Айгуль.</div>'
            f'<div class="cta-row">{cta}</div>'
            '<div class="legend">пороги заказчика: '
            '<span class="dot red"></span><b>рост ≥ 10%</b> — красный флаг '
            '<span class="dot amber"></span><b>рост ≥ 5%</b> '
            '<span class="dot green"></span><b>подешевело ≥ 5%</b></div>'
            + stats
            + '<h2>Отделы</h2>'
            f'<div class="grid">{"".join(cards)}</div>'
            '<footer>hackathon-s26-room-4 · «Чужая боль» 29.08.2026'
            '</footer></div>')
    (site_dir / "index.html").write_text(page, encoding="utf-8")
    return site_dir / "index.html"


def main(argv=None):
    ap = argparse.ArgumentParser(description="собрать дашборд кухни")
    ap.add_argument("--root", default=".")
    ap.add_argument("--site", default="site")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    out = build_site(args.root, args.site)
    print(f"дашборд собран: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
