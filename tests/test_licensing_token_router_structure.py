from central_server.server import app


def test_licensing_token_routes_are_registered_on_main_app():
    paths = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
        if getattr(route, "path", "").startswith("/api/licensing/licenses/")
        or getattr(route, "path", "").startswith("/api/registration-tokens")
        or getattr(route, "path", "") == "/api/register-device"
    }

    expected = {
        ("/api/licensing/licenses/{license_id}/token", ("GET",)),
        ("/api/licensing/licenses/{license_id}/regenerate-token", ("POST",)),
        ("/api/registration-tokens", ("GET",)),
        ("/api/registration-tokens", ("POST",)),
        ("/api/registration-tokens/{token_id}/revoke", ("POST",)),
        ("/api/register-device", ("POST",)),
    }

    assert expected.issubset(paths)
