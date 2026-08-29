"""Очередь подтверждений: где в автоматике стоит человек.

Заказчик НЕ пишет справочник. Он даёт список товаров, которые закупает —
своими словами, как привык. Всё остальное строит инструмент. Но три решения
машина принимать не имеет права, и они выносятся человеку явной очередью,
а не прячутся в логике.

    заказчик добавил товар «Говядина Рибай»
              │
              ▼
    прогон по всем поставщикам (каждая позиция × новый товар)
              │
      ┌───────┼───────────────┬────────────────────┐
      ▼       ▼               ▼                    ▼
   ≥ 0.85   0.60-0.85      < 0.60            вес не указан
  привязали  ГЕЙТ 1        не нашлось          ГЕЙТ 2
  сами       «это тот же   (честно говорим,    «за кг или
             товар?»        что нет)            за упаковку?»

Плюс ГЕЙТ 3 на входе источника: «это поставщик или справочная цена» — от
этого зависит, попадёт ли цена в предложение или останется опорной линией.

**Подтверждение человека живёт.** Ответ записывается в `docs/matching-rules.json`
и применяется дальше сам: один раз сказал «филе цб охл. = куриное филе
охлаждённое» — больше не спрашиваем. Это и есть накопление знания вместо
повторного угадывания.

Почему гейт именно здесь. Автоматическая склейка при уверенности 0.7 звучит
безобидно, но ошибка стоит закупки не того товара по цене другого. А отказ
склеивать молча стоит того, что закупщик не увидит существующее предложение.
Оба исхода дорогие — поэтому среднюю полосу отдаём человеку, и только её.
"""

from __future__ import annotations

import json
from pathlib import Path

from parsers.catalog import canon_title, classify, is_benchmark
from parsers.catalog import to_per_kg
from parsers.matching import AUTO, REVIEW

RULES_PATH = Path("docs/matching-rules.json")


def load_rules(path: Path = RULES_PATH) -> dict:
    """Подтверждения, которые человек уже дал. Спрашивать второй раз нельзя."""
    if not path.exists():
        return {"confirmed": {}, "rejected": {}, "units": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_rules(rules: dict, path: Path = RULES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rules, ensure_ascii=False, indent=1),
                    encoding="utf-8")


def build_queue(snapshots: list[dict], rules: dict | None = None) -> dict:
    """Что требует человека прямо сейчас, разложенное по трём гейтам."""
    rules = rules or load_rules()
    confirmed, rejected = rules.get("confirmed", {}), rules.get("rejected", {})
    units = rules.get("units", {})

    gate_match: list[dict] = []      # гейт 1 — спорная привязка
    gate_unit: list[dict] = []       # гейт 2 — единица измерения
    gate_source: list[dict] = []     # гейт 3 — роль источника
    auto = 0

    seen_sources = set()
    for snap in snapshots:
        source = snap.get("source", "")
        if source not in seen_sources:
            seen_sources.add(source)
            if not is_benchmark(source) and "·" not in source:
                gate_source.append({
                    "source": source,
                    "question": "это поставщик, у которого можно купить, "
                                "или справочная цена?",
                })

        if snap.get("source_status") != "ok":
            continue

        for item in snap.get("items", {}).values():
            title = item.get("title") or ""
            if title in rejected:
                continue
            key = confirmed.get(title) or ""
            if not key:
                key, confidence, decision = classify(title)
                if decision == "на подтверждение" and REVIEW <= confidence < AUTO:
                    gate_match.append({
                        "title": title, "source": source,
                        "suggest": canon_title(key), "key": key,
                        "confidence": confidence,
                        "question": f"«{title[:60]}» — это {canon_title(key)}?",
                    })
                    continue
            if key:
                auto += 1

            price = item.get("price")
            if price is not None and item.get("price_status") == "listed":
                per_kg, how = to_per_kg(title, float(price), source)
                if per_kg is None and title not in units:
                    gate_unit.append({
                        "title": title, "source": source, "price": price,
                        "question": f"«{title[:60]}» — {price} за что? "
                                    f"за кг, за штуку или за упаковку?",
                    })

    return {
        "auto_matched": auto,
        "gate_match": gate_match,
        "gate_unit": gate_unit[:60],
        "gate_source": gate_source,
        "total_questions": len(gate_match) + len(gate_unit) + len(gate_source),
    }


def confirm(title: str, key: str, rules: dict | None = None) -> dict:
    """Человек сказал «да» — записываем, больше не спрашиваем."""
    rules = rules or load_rules()
    rules.setdefault("confirmed", {})[title] = key
    save_rules(rules)
    return rules


def reject(title: str, rules: dict | None = None) -> dict:
    rules = rules or load_rules()
    rules.setdefault("rejected", {})[title] = True
    save_rules(rules)
    return rules
