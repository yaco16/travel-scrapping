from pathlib import Path

from jinja2 import nodes

from travel_scrapping.web.routes import templates


EXPECTED_TEMPLATE_FILTERS = {"price_display", "date_time"}


def test_all_jinja_templates_compile_with_registered_filters():
    for template_name in templates.env.list_templates(filter_func=lambda name: name.endswith(".html")):
        templates.env.get_template(template_name)


def test_template_jinja_filters_are_registered_in_app_environment():
    used_filters: set[str] = set()
    assert templates.env.loader is not None
    for template_name in templates.env.list_templates(filter_func=lambda name: name.endswith(".html")):
        source, _, _ = templates.env.loader.get_source(templates.env, template_name)
        parsed = templates.env.parse(source)
        used_filters.update(node.name for node in parsed.find_all(nodes.Filter))

    assert EXPECTED_TEMPLATE_FILTERS <= used_filters
    assert EXPECTED_TEMPLATE_FILTERS <= set(templates.env.filters)
    assert used_filters <= set(templates.env.filters)


def test_key_ui_elements_exist_in_templates():
    assert templates.env.loader is not None
    results, _, _ = templates.env.loader.get_source(templates.env, "results.html")
    offers, _, _ = templates.env.loader.get_source(templates.env, "_results_offers.html")
    home, _, _ = templates.env.loader.get_source(templates.env, "home.html")
    base, _, _ = templates.env.loader.get_source(templates.env, "base.html")

    assert "hero" in results
    assert "metric-card" in results
    assert "offres affichées sur" in offers
    assert "Meilleur prix" in offers
    assert "Providers désactivés" in results
    assert 'hx-target="#results-offers-panel"' in offers
    assert "mode=train" in offers
    assert "step-spinner" not in results
    assert "status-badge--pending" in results
    assert "Dernier run" in home
    assert "Mode sombre" in base
    assert "data-theme-toggle" in base
    assert "localStorage" in base
    assert 'document.documentElement.dataset.theme' in base
    assert 'value="bus"' in home
    assert 'value="train"' in home
    assert 'value="all"' in home
    assert "deal-card__operator" in offers
    assert "Provider {{ deal.provider_status|provider_status_display }}" not in offers


def test_dark_theme_css_uses_global_theme_attribute():
    css = Path("travel_scrapping/web/static/style.css").read_text()
    assert "[data-theme=dark]" in css
    assert "--color-bg:" in css
    assert "--color-surface:" in css
