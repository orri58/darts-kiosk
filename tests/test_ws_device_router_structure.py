from central_server.server import app


def test_ws_device_route_is_registered_on_main_app():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/ws/devices" in paths
