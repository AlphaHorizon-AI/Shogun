import reflex as rx
from reflex.plugins.sitemap import SitemapPlugin
from shogun.app import create_app

_shogun_app = None

# Transform the Reflex FastAPI app to mount the Shogun API routes
def api_transformer(app):
    global _shogun_app
    if _shogun_app is None:
        _shogun_app = create_app()
    
    # Merge Shogun routers into Reflex
    for route in _shogun_app.router.routes:
        # Avoid duplicate routes if transformer runs multiple times
        if route not in app.router.routes:
            app.router.routes.append(route)
    return app

config = rx.Config(
    app_name="tenshu_ui",
    api_transformer=api_transformer,
    cors_allowed_origins=["*"],
    telemetry_enabled=False,
    disable_plugins=[SitemapPlugin],
    state_auto_setters=False,
)
