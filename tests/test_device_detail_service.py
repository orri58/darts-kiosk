from central_server.services.device_details import safe_json_parse, safe_raw_dt


def test_safe_json_parse_accepts_native_and_string_payloads():
    assert safe_json_parse({"ok": True}) == {"ok": True}
    assert safe_json_parse('[1, 2, 3]') == [1, 2, 3]
    assert safe_json_parse('not-json') is None


def test_safe_raw_dt_returns_none_for_unparseable_values():
    assert safe_raw_dt(None) is None
    assert safe_raw_dt('2026-05-06T12:00:00Z') == '2026-05-06T12:00:00+00:00'
    assert safe_raw_dt('definitely-not-a-date') is None
