# -*- coding: utf-8 -*-
"""Загрузка и нормализация снимков цен.

Контракт снимка v2 (issue #4):
{
  "taken_at": "ISO-8601", "source": "домен", "source_status": "ok|unreachable",
  "items": {"sku": {"shop", "title", "equipment_type" (optional), "price",
                    "currency", "price_status": "listed|on_request|unknown",
                    "in_stock"}}
}

Поддерживаются также:
- v1 (examples/01): {"date", "items": {sku: {shop, price, in_stock}}}
- items списком (docs/evidence-4NNT): [{"sku": ..., ...}, ...]
"""

import json


def _norm_item(sku, raw):
    return {
        "sku": sku,
        "shop": raw.get("shop") or raw.get("source") or "",
        "title": raw.get("title") or sku,
        "equipment_type": raw.get("equipment_type") or "",
        "price": raw.get("price"),
        "currency": raw.get("currency", ""),
        "price_status": raw.get("price_status", "listed"),
        "in_stock": bool(raw.get("in_stock", False)),
    }


def normalize(doc):
    """Любой поддерживаемый формат -> нормализованный снимок."""
    items_raw = doc.get("items", {})
    items = {}
    if isinstance(items_raw, list):
        for raw in items_raw:
            sku = raw.get("sku") or raw.get("id")
            if sku:
                items[sku] = _norm_item(sku, raw)
    else:
        for sku, raw in items_raw.items():
            items[sku] = _norm_item(sku, raw)

    taken_at = doc.get("taken_at", "")
    date = doc.get("date") or (taken_at[:10] if taken_at else "")
    return {
        "date": date,
        "taken_at": taken_at or date,
        "source": doc.get("source", ""),
        "source_status": doc.get("source_status", "ok"),
        "items": items,
    }


def load(path):
    with open(path, encoding="utf-8") as f:
        return normalize(json.load(f))
