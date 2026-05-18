from central_server.server import app


EXPECTED = {
    ("/api/config/profiles", ("GET",)),
    ("/api/config/profile/{scope_type}/{scope_id}", ("PUT",)),
    ("/api/config/history/{scope_type}/{scope_id}", ("GET",)),
    ("/api/config/rollback/{scope_type}/{scope_id}/{version}", ("POST",)),
    ("/api/config/diff/{scope_type}/{scope_id}", ("GET",)),
    ("/api/config/import/validate", ("POST",)),
    ("/api/config/import/apply", ("POST",)),
}


def test_config_profile_routes_are_registered_on_main_app():
    paths = {
        (route.path, tuple(sorted(route.methods or [])))
        for route in app.routes
    }

    for expected in EXPECTED:
        assert expected in paths
