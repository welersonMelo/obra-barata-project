from app.services.pricing.suppliers import (
    COMERCIAL_ALIANCA_BASE_URL,
    _parse_amount_unit,
    _parse_unit_family,
    build_product_search_text,
    enrich_offer_for_material,
    purchase_quantity_for_material,
    _scrape_storefront_search_offers,
    _scrape_tray_datalayer_offers,
    _title_matches_material_query,
)
from app.models.materials import MaterialObra, OfertaFornecedor


def test_storefront_scraper_ignores_navigation_categories_for_rejunte():
    html = """
    <html>
      <body>
        <nav>
          <a href="/ferramentas">Ferramentas</a>
          <a href="/acabamentos">Acabamentos</a>
        </nav>
        <main>
          <article class="product-card">
            <a href="/rejunte-flexivel-votorantim-branco-1kg">
              Rejunte Flexivel Votorantim Branco 1kg
            </a>
            <strong>R$ 10,90</strong>
          </article>
        </main>
      </body>
    </html>
    """

    offers = _scrape_storefront_search_offers(
        html=html,
        query="Rejunte 15saco 1 kg",
        base_url=COMERCIAL_ALIANCA_BASE_URL,
        supplier_name="Comercial Alianca",
        fallback_unit="saco 1 kg",
        default_installments=10,
        limit=5,
    )

    assert len(offers) == 1
    assert offers[0].descricao == "Rejunte Flexivel Votorantim Branco 1kg"
    assert offers[0].valor_unitario == 10.9
    assert offers[0].link_produto == (
        "https://www.comercialalianca.com/rejunte-flexivel-votorantim-branco-1kg"
    )


def test_storefront_scraper_returns_empty_when_only_category_matches_unit():
    html = """
    <html>
      <body>
        <nav>
          <a href="/ferramentas">Ferramentas</a>
          <a href="/acabamentos">Acabamentos</a>
        </nav>
        <section>
          <a href="/misturador-de-tinta-60x400mm-fertak">Misturador de Tinta</a>
          <strong>R$ 23,90</strong>
        </section>
      </body>
    </html>
    """

    offers = _scrape_storefront_search_offers(
        html=html,
        query="Rejunte 15saco 1 kg",
        base_url=COMERCIAL_ALIANCA_BASE_URL,
        supplier_name="Comercial Alianca",
        fallback_unit="saco 1 kg",
        default_installments=10,
        limit=5,
    )

    assert offers == []


def test_tray_datalayer_scraper_filters_unrelated_products():
    html = """
    <html>
      <body>
        <script>
          var dataLayer = [{
            "listProducts": [
              {
                "nameProduct": "Ferramenta Multiuso",
                "sellPrice": "23.90",
                "urlProduct": "/ferramenta-multiuso"
              },
              {
                "nameProduct": "Rejunte Flexivel Votorantim Preto 1kg",
                "sellPrice": "10.90",
                "urlProduct": "/rejunte-flex-tpii-rev-pt-1kg-votorantim"
              }
            ]
          }];
        </script>
      </body>
    </html>
    """

    offers = _scrape_tray_datalayer_offers(
        html=html,
        query="Rejunte 15saco 1 kg",
        supplier_name="Comercial Alianca",
        base_url=COMERCIAL_ALIANCA_BASE_URL,
        fallback_unit="saco 1 kg",
        default_installments=10,
        limit=5,
    )

    assert [offer.descricao for offer in offers] == [
        "Rejunte Flexivel Votorantim Preto 1kg"
    ]


def test_title_match_ignores_stopwords_and_allows_singular_plural():
    assert _title_matches_material_query(
        "Dobradiças para portas",
        "Dobradica zincada 3 polegadas",
    )
    assert not _title_matches_material_query(
        "Dobradiças para portas",
        "Torneira para cozinha cromada",
    )


def test_build_product_search_text_prefers_product_identity_and_package_size():
    search_text = build_product_search_text(
        nome="Pintura interna (tinta acrilica)",
        descricao="Tinta para paredes internas",
        quantidade=3,
        medida="lata 18 L",
        fornecedor="Comercial Alianca",
    )

    assert search_text == "tinta acrilica 18L"


def test_build_product_search_text_uses_package_size_not_required_package_count():
    search_text = build_product_search_text(
        nome="Rejunte",
        descricao="Preenchimento de juntas de revestimento ceramico",
        quantidade=15,
        medida="saco 1 kg",
    )

    assert search_text == "Rejunte 1kg"


def test_build_product_search_text_does_not_duplicate_existing_package_size():
    search_text = build_product_search_text(
        nome="Tinta acrilica 18 litros",
        descricao="Tinta para paredes internas",
        quantidade=3,
        medida="lata 18 L",
    )

    assert search_text == "Tinta acrilica 18 litros"


def test_unit_parser_supports_cubic_meters():
    assert _parse_unit_family("m3") == "m3"
    assert _parse_amount_unit("2,5 m3") == (2.5, "m3")


def test_pipe_search_rejects_accessory_and_keeps_the_pipe_product():
    query = "Tubo PVC soldavel 25 mm 6 m"

    assert not _title_matches_material_query(
        query,
        "Abracadeira para Tubo Soldavel 25mm - Tigre",
    )
    assert _title_matches_material_query(
        query,
        "Cano PVC 25 mm x 6 m Soldavel - Tigre",
    )


def test_purchase_quantity_keeps_explicit_bar_count():
    assert purchase_quantity_for_material(8, "barra 6 m", "6 m") == 8

    offer = enrich_offer_for_material(
        MaterialObra(nome="Tubo PVC soldavel 25 mm", quantidade=8, medida="barra 6 m"),
        OfertaFornecedor(
            fornecedor="Grupo Pisolar",
            descricao="Cano PVC 25 mm x 6 m Soldavel - Tigre",
            unidade="6 m",
            quantidade=2,
            valor_unitario=28.45,
        ),
    )

    assert offer.quantidade == 8
    assert offer.valor_total == 227.6
    assert offer.preco_a_vista == 227.6
    assert offer.preco_a_prazo == 227.6


def test_purchase_quantity_keeps_explicit_package_count():
    assert purchase_quantity_for_material(10, "pct", "pct") == 10
