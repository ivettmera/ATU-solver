"""
Smoke de la API: el esquema OpenAPI se genera y expone los contratos esperados.

No se usa TestClient para evitar arrancar el lifespan (Redis/scheduler): la generación del
OpenAPI no requiere infraestructura y basta para validar que los endpoints están montados y
que el equipo móvil/frontend puede consumir los contratos.
"""

from app.main import create_app


def test_openapi_expone_endpoints():
    app = create_app()
    spec = app.openapi()
    rutas = spec["paths"]

    assert "/api/v1/telemetry/ingress" in rutas
    assert "/api/v1/incidents" in rutas
    assert "/api/v1/dispatch/recommendations" in rutas
    assert "/api/v1/red/estaciones" in rutas
    assert "/api/v1/red/config" in rutas
    assert "/health" in rutas


def test_dashboard_html_existe():
    from pathlib import Path

    import app.main as main_mod

    assert (main_mod.STATIC_DIR / "dashboard.html").is_file()


def test_schemas_registrados_en_openapi():
    app = create_app()
    spec = app.openapi()
    componentes = spec["components"]["schemas"]

    for modelo in ("TelemetryPayload", "IncidentReport", "DispatchPlan"):
        assert modelo in componentes
