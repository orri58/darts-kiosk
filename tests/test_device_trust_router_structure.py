from central_server.server import app


def test_device_trust_read_routes_are_registered_on_main_app():
    paths = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/device-trust")
    }

    expected = {
        ("/api/device-trust/enroll", ("POST",)),
        ("/api/device-trust/devices/{device_id}", ("GET",)),
        ("/api/device-trust/devices/{device_id}/support-diagnostics", ("GET",)),
        ("/api/device-trust/devices/{device_id}/issue-credential", ("POST",)),
        ("/api/device-trust/devices/{device_id}/issue-lease", ("POST",)),
        ("/api/device-trust/devices/{device_id}/revoke-credential", ("POST",)),
        ("/api/device-trust/devices/{device_id}/revoke-lease", ("POST",)),
        ("/api/device-trust/lease/current", ("GET",)),
    }

    assert expected.issubset(paths)
