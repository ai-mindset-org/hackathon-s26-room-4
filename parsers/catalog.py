"""Справочник товаров: сводит позиции разных поставщиков к одной строке.

`matching.py` отвечает на вопрос «эти две строки — один товар?». Этого мало:
поставщиков много, и попарное сравнение даёт кашу. Нужен **канон** — список
товаров закупщика, к которому притягивается всё остальное.

Работает так:

    позиция поставщика ──► признаки (вид · отруб · обработка)
                            │
                            ▼
                     канонический товар          ──► строка дайджеста
    «Мясо Кур (бройлеры)»      ┐
    «Тушка цыплёнка охл.»      ├──► КУРИЦА · ТУШКА ──► 138 ₽ Фуд Сити
    «Курица, тушка целиком»    ┘                       294 ₽ ВкусВилл
                                                       262 ₽ Росстат (эталон)

Канон задаёт ЗАКАЗЧИК, а не мы: это его номенклатура, его слова. Список ниже
собран из того, что прислал заказчик 4NNT (мясо/рыба/курица) и из позиций,
реально встреченных у подключённых поставщиков.

Позиция, не привязавшаяся ни к одному канону с уверенностью ≥0.6, не
выбрасывается и не приклеивается наугад — она попадает в «неопознанные», и это
видно в отчёте. Молчаливая склейка хуже пропуска: закупщик примет решение по
чужому товару.
"""

from __future__ import annotations

from parsers.matching import AUTO, REVIEW, score

# ── Канонический справочник отдела 🥩 ────────────────────────────────────────
# key: (что показываем человеку, вид, отруб, обработка)
CANON = {
    "kurica-tushka":   ("Курица, тушка", "курица", "тушка", ""),
    "kurica-file":     ("Курица, филе грудки", "курица", "филе-грудки", ""),
    "kurica-okorochka":("Курица, окорочка", "курица", "окорочка", ""),
    "indeyka-file":    ("Индейка, филе", "индейка", "филе", ""),
    "govyadina-vyrezka":("Говядина, вырезка", "говядина", "вырезка", ""),
    "govyadina-ribay": ("Говядина, рибай", "говядина", "рибай", ""),
    "govyadina-lopatka":("Говядина, лопатка", "говядина", "лопатка", ""),
    "govyadina-tusha": ("Говядина, туша", "говядина", "тушка", ""),
    "svinina-tusha":   ("Свинина, туша", "свинина", "тушка", ""),
    "svinina-sheyka":  ("Свинина, шейка", "свинина", "шейка", ""),
    "baranina":        ("Баранина", "баранина", "", ""),
    "losos-file":      ("Лосось, филе", "лосось", "филе", ""),
    "forel-file":      ("Форель, филе", "форель", "филе", ""),
    "treska-tushka":   ("Треска, тушка", "треска", "тушка", ""),
    "treska-file":     ("Треска, филе", "треска", "филе", ""),
    "mintay-file":     ("Минтай, филе", "минтай", "филе", ""),
    "gorbusha":        ("Горбуша", "горбуша", "", ""),
    "skumbriya":       ("Скумбрия", "скумбрия", "", ""),
    "krevetka":        ("Креветка", "креветка", "", ""),
}

# Эталоны не продают — их цена идёт справкой, а не предложением.
BENCHMARK_MARKS = ("эталон", "потолок")


def canon_title(key: str) -> str:
    if key in CANON:
        return CANON[key][0]
    parts = [p for p in str(key).split("-") if p]
    return " · ".join(p.capitalize() if i == 0 else p
                      for i, p in enumerate(parts)) or key


def _canon_phrase(key: str) -> str:
    """Каноническая позиция в виде фразы — чтобы сравнивать тем же матчером."""
    _, view, cut, state = CANON[key]
    return " ".join(x for x in (view, cut, state) if x)


def classify(title: str) -> tuple[str, float, str]:
    """Позиция поставщика → (ключ канона, уверенность, решение).

    Канон не список, а ПРОИЗВОДНАЯ от таксономии. Ручной список из двух десятков
    строк был тупиком: словарь видов вырос до тридцати, «Корюшку» мы узнавали,
    а привязать было не к чему — 61% позиций падали в «не опознано» не потому,
    что непонятны, а потому что канона под них никто не завёл.

    Теперь порядок обратный: сначала пробуем ручной канон заказчика (его
    номенклатура главнее), и только если не сошлось — собираем ключ из
    признаков «вид + отруб». Товар, у которого опознан хотя бы вид, всегда
    получает строку.
    """
    best_key, best = "", 0.0
    for key in CANON:
        value = score(title, _canon_phrase(key))["score"]
        if value > best:
            best_key, best = key, value
    if best >= AUTO:
        return best_key, round(best, 3), "совпало"

    from parsers.matching import features
    f = features(title)
    if f["view"]:
        key = "-".join(x for x in (f["view"], f["cut"]) if x)
        if best >= REVIEW and best_key:
            return best_key, round(best, 3), "на подтверждение"
        return key, 0.7, "собран из признаков"

    if best >= REVIEW:
        return best_key, round(best, 3), "на подтверждение"
    return "", round(best, 3), "не опознано"


def is_benchmark(source: str) -> bool:
    return any(mark in str(source or "").lower() for mark in BENCHMARK_MARKS)


def build(snapshots: list[dict]) -> dict:
    """Все снимки → строки по каноническим товарам + неопознанное."""
    rows: dict[str, list[dict]] = {}
    unknown: list[dict] = []
    silent = [s["source"] for s in snapshots if s.get("source_status") != "ok"]

    for snap in snapshots:
        if snap.get("source_status") != "ok":
            continue
        source = snap.get("source", "")
        for item in snap.get("items", {}).values():
            title = item.get("title") or ""
            price = item.get("price")
            if item.get("price_status") != "listed" or price is None:
                continue
            key, confidence, decision = classify(title)
            offer = {
                "source": source, "shop": item.get("shop") or source,
                "title": title, "price": float(price),
                "currency": item.get("currency", "RUB"),
                "benchmark": is_benchmark(source),
                "confidence": confidence, "decision": decision,
            }
            if key:
                rows.setdefault(key, []).append(offer)
            else:
                unknown.append(offer)

    result = []
    for key, offers in rows.items():
        real = [o for o in offers if not o["benchmark"] and o["currency"] == "RUB"]
        marks = [o for o in offers if o["benchmark"]]
        real.sort(key=lambda o: o["price"])
        best = real[0] if real else None
        worst = real[-1] if real else None
        result.append({
            "key": key, "title": canon_title(key),
            "offers": real, "benchmarks": marks,
            "best": best, "worst": worst,
            "spread_percent": (round((worst["price"] / best["price"] - 1) * 100, 1)
                               if best and worst and best["price"] else 0.0),
            "needs_review": [o for o in offers if o["decision"] == "на подтверждение"],
        })

    result.sort(key=lambda r: -len(r["offers"]))
    return {"rows": result, "unknown": unknown, "silent_sources": silent,
            "sources_total": len(snapshots),
            "sources_ok": len(snapshots) - len(silent)}


# ── Приведение к килограмму ──────────────────────────────────────────────────
# Без этого справочник врёт грубее, чем помогает: «Минтай филе 600 г за 597 ₽»
# и «минтай филе 145 ₽/кг» дают разброс 389%, которого в реальности нет.
# Цена за упаковку делится на её вес; позиция без веса и без явного «/кг»
# в сравнение НЕ идёт — помечается и показывается отдельно.

import re as _re

_WEIGHT = _re.compile(
    r"(\d+[.,]?\d*)\s?(кг|kg|г\b|гр\b|g\b|мл\b|л\b)", _re.IGNORECASE)
_PER_KG = ("/кг", " кг", "руб./кг", "₽/кг", "за кг", "100kg", "100 кг")


def to_per_kg(title: str, price: float, source: str = "") -> tuple[float | None, str]:
    """(цена за кг, как получили). None — привести нельзя, в сравнение не идёт."""
    low = f"{title} {source}".lower()
    if any(mark in low for mark in _PER_KG):
        return price, "уже за кг"

    match = _WEIGHT.search(title or "")
    if not match:
        return None, "вес не указан"

    value = float(match.group(1).replace(",", "."))
    unit = match.group(2).lower()
    kilos = value if unit in ("кг", "kg", "л") else value / 1000
    if kilos <= 0:
        return None, "вес не разобрался"

    per_kg = round(price / kilos, 2)

    # Санитарный предел. Еда не стоит 25 000 ₽ за килограмм и не стоит 5 ₽:
    # такие числа означают, что вес из названия взят не тот — «Сыр 15 г» в
    # описании дал 24 900 ₽/кг, и инструмент подал это как разброс 6817%.
    # Число вне коридора не выбрасывается, а отправляется человеку с причиной.
    if not (20 <= per_kg <= 20000):
        return None, (f"после приведения вышло {per_kg:,.0f} ₽/кг — "
                      f"вес в названии похож на ошибку".replace(",", " "))
    return per_kg, f"из цены за {match.group(0)}"


def build_per_kg(snapshots: list[dict]) -> dict:
    """То же, что build(), но все цены приведены к килограмму.

    Позиции, которые привести нельзя, не выбрасываются — они уходят в
    `not_comparable` и показываются человеку отдельной строкой. Молча ронять
    товар нельзя: закупщик решит, что его никто не продаёт.
    """
    data = build(snapshots)
    not_comparable: list[dict] = []

    for row in data["rows"]:
        for bucket in ("offers", "benchmarks"):
            kept = []
            for offer in row[bucket]:
                per_kg, how = to_per_kg(offer["title"], offer["price"],
                                        offer["source"])
                if per_kg is None:
                    not_comparable.append(dict(offer, reason=how))
                    continue
                kept.append(dict(offer, price=per_kg, unit="₽/кг", basis=how))
            kept.sort(key=lambda o: o["price"])
            row[bucket] = kept

        row["best"] = row["offers"][0] if row["offers"] else None
        row["worst"] = row["offers"][-1] if row["offers"] else None
        row["spread_percent"] = (
            round((row["worst"]["price"] / row["best"]["price"] - 1) * 100, 1)
            if row["best"] and row["worst"] and row["best"]["price"] else 0.0)

    data["rows"] = [r for r in data["rows"] if r["offers"]]
    data["rows"].sort(key=lambda r: -len(r["offers"]))
    data["not_comparable"] = not_comparable
    return data
