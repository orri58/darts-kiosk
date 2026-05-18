from central_server.server import app


def test_effective_config_route_is_registered_on_main_app():
    paths = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if getattr(route, "path", "") == "/api/config/effective"
    }

    assert ("/api/config/effective", ("GET",)) in paths
