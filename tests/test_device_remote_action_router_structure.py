from central_server.server import app


def test_device_remote_action_routes_are_registered_on_main_app():
    paths = {(route.path, tuple(sorted(route.methods or []))) for route in app.routes if getattr(route, "path", "").startswith("/api/remote-actions")}

    expected = {
        ("/api/remote-actions/{device_id}/pending", ("GET",)),
        ("/api/remote-actions/{device_id}/ack", ("POST",)),
    }

    assert expected.issubset(paths)
