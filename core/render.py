# -*- coding: utf-8 -*-
"""Статическая HTML-страница дайджеста. Стиль: core/theme.py (референс
dfinity.org), интерактивный canvas-слой в духе canvas-ui."""

import html as _html

from core import theme


def _line_html(sev, line):
    txt = _html.escape(line)
    while "**" in txt:
        txt = txt.replace("**", "<b>", 1).replace("**", "</b>", 1)
    return f'<li class="{sev}">{txt}</li>'


def _stat(label, value, cls=""):
    return (f'<div class="stat"><div class="label">{label}</div>'
            f'<div class="value {cls}">{value}</div></div>')


def to_html(d, title="Мониторинг → дайджест · комната 4", back="index.html",
            extra_link=None):
    c = d["counts"]
    honest = d["sources_ok"] < d["sources_total"]
    parts = [theme.head(_html.escape(title)), theme.CANVAS,
             '<div class="page">',
             f'<a class="back" href="{back}">← Кухня</a>',
             f"<h1>{_html.escape(title)}</h1>",
             f'<div class="lede">{d["date_from"]} → {d["date_to"]} · пороги '
             f'заказчика K4UR: <span class="dot red"></span> рост ≥ '
             f'{d["thresholds"]["red"]:g}% <span class="dot amber"></span> '
             f'рост ≥ {d["thresholds"]["warn"]:g}% <span class="dot green">'
             f'</span> подешевело ≥ {d["thresholds"]["warn"]:g}%</div>',
             (f'<div class="lede"><a class="dash-link" href="{extra_link[0]}">'
              f'{extra_link[1]}</a></div>' if extra_link else ""),
             '<div class="stats">',
             _stat("подорожало сильно", c["red"], "grad" if c["red"] else ""),
             _stat("подорожало", c["warn"]),
             _stat("подешевело", c.get("deal", 0)),
             _stat("без изменений", d["unchanged"]),
             _stat("источники", f'{d["sources_ok"]}/{d["sources_total"]}'),
             "</div>"]
    if honest:
        parts.append('<div class="warnbox">⚠️ Картина неполная: часть '
                     'источников сегодня не удалось посмотреть — их позиции '
                     'НЕ считаются пропавшими.</div>')
    for source, lines in d["sections"]:
        parts.append(f"<h2>{_html.escape(source or 'источник')}</h2>"
                     '<ul class="digest">')
        parts.extend(_line_html(sev, line) for sev, line in lines)
        if not lines:
            parts.append("<li>изменений нет</li>")
        parts.append("</ul>")
    if d["unchanged"]:
        parts.append(f'<div class="unchanged">Без изменений: {d["unchanged"]} '
                     'позиций — свернуто.</div>')
    cs = d.get("cross_shop")
    if cs and cs["rows"]:
        parts.append('<h2>Один товар в разных магазинах (сегодня)</h2>'
                     '<ul class="digest">')
        for r in cs["rows"]:
            if r["shops_compared"] < 2:
                continue
            cur = f' {r["currency"]}' if r["currency"] else ""
            parts.append(_line_html("info",
                f'{r["sku"]}: от {r["cheapest"]["price"]:g} ({r["cheapest"]["shop"]}) '
                f'до {r["dearest"]["price"]:g} ({r["dearest"]["shop"]}){cur} — '
                f'разброс **+{r["spread_percent"]:g}%** по {r["shops_compared"]} магазинам'))
        if cs["silent_sources"]:
            parts.append(_line_html("warn",
                f'⚠️ без данных сегодня: {", ".join(cs["silent_sources"])} '
                f'({len(cs["silent_sources"])} из {cs["sources_total"]})'))
        parts.append("</ul>")
    parts.append('<footer>hackathon-s26-room-4 · «Чужая боль» 29.08.2026'
                 '</footer></div>')
    return "\n".join(parts)
