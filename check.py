#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Приёмка комнаты 4 одним запуском: python3 check.py

Гоняет инструмент по examples/ и сверяет ФАКТЫ с expected.md.
Только стандартная библиотека, pytest не нужен. Выход: «прошло N из M»,
код возврата 0 при полном прохождении.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
results = []


def case(name):
    def wrap(fn):
        try:
            fn()
            results.append((name, True, ""))
        except Exception as e:  # noqa: BLE001 — приёмке важен вердикт, не трейс
            results.append((name, False, f"{type(e).__name__}: {e}"))
    return wrap


@case("01 снимки цен: дифф, %, пропажа/новинка не перепутаны")
def _01():
    from core.fallback_diff import diff_snapshots
    from core.snapshot import load
    a = load(ROOT / "examples/01-снимки-цен/input/snapshot-2026-08-27.json")
    b = load(ROOT / "examples/01-снимки-цен/input/snapshot-2026-08-28.json")
    ev = {(e["type"], e["sku"]): e for e in diff_snapshots(a, b)}
    assert ev[("price_change", "MZ7L3960HCJR-00A07")]["pct"] == -5.3
    assert ev[("price_change", "ST16000NM004J")]["pct"] == 6.0
    assert ("back_in_stock", "ST12000NM004J") in ev
    assert ("gone", "MZ7L33T8HBLT-00A07") in ev, "пропажа ≠ снижение цены"
    assert ev[("new_item", "ST24000NM002H")]["to"] == 68900
    assert len(ev) == 5, f"лишние события: {sorted(ev)}"


@case("02 парсинг вёрстки: NBSP, старая цена, «ожидается» = нет")
def _02():
    from parsers.cards import parse_card
    d = ROOT / "examples/02-парсинг-вёрстки/input"
    a = parse_card((d / "card-a.html").read_text(encoding="utf-8"))
    assert a["sku"] == "MZ7L3960HCJR-00A07"
    assert a["price"] == 32100, "взята зачёркнутая старая цена!"
    assert a["in_stock"] is True
    b = parse_card((d / "card-b.html").read_text(encoding="utf-8"))
    assert b["sku"] == "ST16000NM004J" and b["price"] == 42200
    assert b["in_stock"] is False, "«ожидается поставка» — это НЕ в наличии"


@case("03 время из логов: оба порога, границы блоков, число только с N")
def _03():
    from timelog.__main__ import read_events
    from timelog.blocks import build_blocks, total_minutes
    events = read_events(ROOT / "examples/03-время-из-логов/input/sessions.jsonl")
    b10 = build_blocks(events, gap_minutes=10)
    assert [x.label for x in b10] == ["09:00–09:05", "09:41–09:44",
                                      "11:10–11:59", "14:00–14:03"]
    assert abs(total_minutes(b10) - 59.5) < 0.5
    b40 = build_blocks(events, gap_minutes=40)
    assert [x.label for x in b40] == ["09:00–09:44", "11:10–11:59",
                                      "14:00–14:03"]
    assert abs(total_minutes(b40) - 96.0) < 0.5


passed = sum(1 for _, ok, _ in results if ok)
for name, ok, err in results:
    print(("✅" if ok else "❌"), name, ("— " + err if err else ""))
print(f"\nпрошло {passed} из {len(results)}")
sys.exit(0 if passed == len(results) else 1)
