from central_server.server import app


def test_device_detail_route_is_registered_on_main_app():
    paths = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if getattr(route, "path", "") == "/api/telemetry/device/{device_id}"
    }

    assert ("/api/telemetry/device/{device_id}", ("GET",)) in paths
