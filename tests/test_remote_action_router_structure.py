from central_server.server import app


def test_remote_action_routes_are_registered_on_main_app():
    paths = {(route.path, tuple(sorted(route.methods or []))) for route in app.routes if getattr(route, "path", "").startswith("/api/remote-actions")}

    expected = {
        ("/api/remote-actions/bulk", ("POST",)),
        ("/api/remote-actions/overview", ("GET",)),
        ("/api/remote-actions/review-queue", ("GET",)),
        ("/api/remote-actions/{device_id}", ("GET",)),
        ("/api/remote-actions/{device_id}", ("POST",)),
        ("/api/remote-actions/{action_id}/review", ("POST",)),
        ("/api/remote-actions/{device_id}/summary", ("GET",)),
        ("/api/remote-actions/{device_id}/history", ("GET",)),
        ("/api/remote-actions/{device_id}/pending", ("GET",)),
        ("/api/remote-actions/{device_id}/ack", ("POST",)),
    }

    assert expected.issubset(paths)
