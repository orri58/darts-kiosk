from central_server.server import app


def test_ws_status_routes_are_registered_on_main_app():
    paths = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/ws")
    }

    expected = {
        ("/api/ws/status", ("GET",)),
        ("/api/ws/device/{device_id}", ("GET",)),
    }

    assert expected.issubset(paths)
