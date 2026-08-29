"""Приёмка пяти новых источников — на сохранённых кусках HTML, без сети.

Фикстуры — вырезки реальной вёрстки каждого сайта (проверено curl'ом 29.08),
не выдуманные упрощения. Каждый модуль проверяется минимум дважды: разбор
позиции и одна из его ловушек (единица измерения, невидимые символы,
фильтр «Продам»/«Куплю», привязка товара к своей компании).
"""

from parsers.snapshot import build_snapshot


# ---------------------------------------------------------------- rosfrukt --

def test_rosfrukt_gallery_caption_keeps_unit_unspoken():
    from parsers.rosfrukt import parse_gallery

    html = '<div class="caption note" itemprop="description">курица тушка 79р</div>'
    items = parse_gallery(html)
    assert len(items) == 1
    assert items[0]["price"] == 79.0
    assert "единица не указана" in items[0]["title"]


def test_rosfrukt_vegetables_reads_schema_price_and_skips_the_stray_first_name():
    from parsers.rosfrukt import parse_vegetables

    html = """
    <div class="ul-w-gallery"><div itemprop="name"></div></div>
    <div class="ul-goods-view-title"><div itemprop="name" >Картофель&nbsp;</div></div>
    <div class="ul-goods-view-price" itemprop="offers">
      <div class="price-small">от 17 руб.</div>
      <meta itemprop="price" content="17">
      <meta itemprop="priceCurrency" content="RUB">
    </div>
    <div class="ul-goods-view-title"><div itemprop="name" >морковь</div></div>
    <div class="ul-goods-view-price" itemprop="offers">
      <div class="price-small">от 19 руб.</div>
      <meta itemprop="price" content="19">
      <meta itemprop="priceCurrency" content="RUB">
    </div>
    """
    items = parse_vegetables(html)
    by_sku = {i["sku"]: i for i in items}
    assert set(by_sku) == {"картофель", "морковь"}
    assert by_sku["картофель"]["price"] == 17.0
    assert by_sku["морковь"]["price"] == 19.0


# ---------------------------------------------------------------- agrosbit --

AGROSBIT_CARD = """
<div itemscope itemtype="https://schema.org/Product">
  <a itemprop="url" title="Огурец Саунд F1" href="https://agrosbit.ru/vegetables/ogurets/ogurec-saund-f1"></a>
  <span itemprop="category">Огурец</span>
  <span itemprop="name">Огурец Саунд F1</span>
  <meta itemprop="description" content="Огурец Саунд F1, калибр 6-12
тел. 89270606681">
  <div class="lot-price" itemscope itemtype="https://schema.org/Offer">
    <span class="lot-price-count" itemprop="price" content="45">45,00
      <span class="lot-price-currency" itemprop="priceCurrency" content="RUB"></span>
    </span>
    <span class="lot-price-unit pl-1">/ т.</span>
  </div>
  <span>{offer_type}</span>
</div>
"""


def test_agrosbit_keeps_unit_as_is_and_reads_phone_from_description():
    from parsers.agrosbit import parse

    items = parse(AGROSBIT_CARD.format(offer_type="Продам"))
    assert len(items) == 1
    item = items[0]
    assert item["sku"] == "ogurec-saund-f1"
    assert item["price"] == 45.0
    assert "/ т." in item["title"]
    assert "89270606681" in item["shop"]


def test_agrosbit_drops_kuplyu_requests_they_are_not_a_supply_price():
    from parsers.agrosbit import parse

    items = parse(AGROSBIT_CARD.format(offer_type="Куплю"))
    assert items == []


# --------------------------------------------------------------- alligator --

ALLIGATOR_CARD = """
<meta itemprop="priceCurrency" content="RUR">
<meta itemprop="lowPrice" content="75.00">
<div class="ProductItem__code label">
  3504.116.21679.1
</div>
<div itemprop="name" class="ProductItem__title">
  Морковь резаная с/м
</div>
<div class="ProductItemForClient__in-stock-quantity">
  8,200 кг.
</div>
"""


def test_alligator_reads_sku_code_price_and_stock_unit():
    from parsers.alligator import parse

    items = parse(ALLIGATOR_CARD)
    assert len(items) == 1
    item = items[0]
    assert item["sku"] == "3504.116.21679.1"
    assert item["price"] == 75.0
    assert "8,200 кг." in item["title"]
    assert item["in_stock"] is True


def test_alligator_skips_cards_without_a_name():
    from parsers.alligator import parse

    html = ALLIGATOR_CARD.replace("Морковь резаная с/м", "")
    assert parse(html) == []


# ---------------------------------------------------------------- vosttorg --

VOSTTORG_CARD = """
<input type="hidden" name="product_data[867][product_id]" value="867" />
<img class="ty-pict img-ab-hover-gallery cm-image" alt="Масло сливочное Ренферли 82,5% 400 г" src="x.jpg" />
<span id="sec_discounted_price_867" class="ty-price-num">&zwj;250&zwj;</span>
<span id="sec_discounted_price_867_for_item" class="ty-price-num">
  за 1 шт.
</span>
"""

VOSTTORG_FOUR_DIGIT = """
<input type="hidden" name="product_data[649][product_id]" value="649" />
<img class="ty-pict img-ab-hover-gallery cm-image" alt="Сыр Чеддер Ред Молочный Мир 3,5 кг" src="x.jpg" />
<span id="sec_price_649" class="ty-price-num">1&nbsp;750</span>
<span id="sec_price_649_for_item" class="ty-price-num">
  за 1 шт.
</span>
"""


def test_vosttorg_strips_zero_width_joiner_around_the_price():
    from parsers.vosttorg import parse

    items = parse(VOSTTORG_CARD)
    assert len(items) == 1
    assert items[0]["price"] == 250.0
    assert items[0]["title"].startswith("Масло сливочное Ренферли")
    assert "за 1 шт." in items[0]["title"]


def test_vosttorg_strips_nbsp_thousand_separator_too():
    """Тот же сайт для четырёхзначных цен использует &nbsp; вместо &zwj;."""
    from parsers.vosttorg import parse

    items = parse(VOSTTORG_FOUR_DIGIT)
    assert items[0]["price"] == 1750.0


# ----------------------------------------------------------- foodsuppliers --

FOODSUPPLIERS_PAGE = """
<div class="content-list-item enterprise-teaser enterprise-tovar-teaser">
  <a class="title-site--h3">Марс Глобал Трейд</a>
  <a href="/tovar/svinaya-obolochka-evropeyskoe-kachestvo-mars-global-treyd" class="title-site--h4">Свиная оболочка европейское качество</a>
  <div class="content-prod__price"><div class="field field-name-field-goods-cost">
    <div class="field-items"><div class="field-item even" >от 15.00 руб.          </div></div>
  </div></div>
</div>
<div class="content-list-item enterprise-teaser enterprise-tovar-teaser">
  <a class="title-site--h3">Георгиевский хлебокомбинат</a>
  <a href="/tovar/sushki-malyshka" class="title-site--h4">Сушки Малышка</a>
  <div class="content-prod__price"><div class="field field-name-field-goods-cost">
    <div class="field-items"><div class="field-item even" >от 65.00 руб.          </div></div>
  </div></div>
  <a href="/tovar/suhari-vanilnye" class="title-site--h4">Сухари ванильные</a>
  <div class="content-prod__price"><div class="field field-name-field-goods-cost">
    <div class="field-items"><div class="field-item even" >от 68.00 руб.          </div></div>
  </div></div>
</div>
"""


def test_foodsuppliers_attaches_each_product_to_its_own_company():
    from parsers.foodsuppliers import parse

    items = parse(FOODSUPPLIERS_PAGE)
    assert len(items) == 3
    by_sku = {i["sku"]: i for i in items}
    assert by_sku["svinaya-obolochka-evropeyskoe-kachestvo-mars-global-treyd"]["shop"] \
        == "Марс Глобал Трейд"
    assert by_sku["sushki-malyshka"]["shop"] == "Георгиевский хлебокомбинат"
    assert by_sku["suhari-vanilnye"]["shop"] == "Георгиевский хлебокомбинат"


def test_foodsuppliers_price_on_request_is_null_not_zero():
    from parsers.foodsuppliers import parse

    page = FOODSUPPLIERS_PAGE.replace("от 15.00 руб.", "Цена по запросу")
    items = parse(page)
    by_sku = {i["sku"]: i for i in items}
    item = by_sku["svinaya-obolochka-evropeyskoe-kachestvo-mars-global-treyd"]
    assert item["price"] is None
    assert item["price_status"] == "on_request"


# ------------------------------------------------------- контракт v2 общее --

def test_all_five_snapshots_match_contract_v2_when_source_is_unreachable():
    """Пустая страница -> unreachable, а не ok с пустыми items (issue #4)."""
    from parsers.rosfrukt import parse_gallery
    from parsers.agrosbit import parse as parse_agrosbit
    from parsers.alligator import parse as parse_alligator
    from parsers.vosttorg import parse as parse_vosttorg
    from parsers.foodsuppliers import parse as parse_foodsuppliers

    for parse_fn in (parse_gallery, parse_agrosbit, parse_alligator,
                     parse_vosttorg, parse_foodsuppliers):
        items = parse_fn("<html></html>")
        assert items == []
        snap = build_snapshot("тест", items, status="ok" if items else "unreachable")
        assert snap["source_status"] == "unreachable"
        assert snap["items"] == {}
