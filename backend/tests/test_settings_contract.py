from backend.services.settings_contract import (
    build_customization_bundle_from_values,
    normalize_customization_bundle,
    normalize_setting_value,
)


def test_kiosk_layout_is_deep_merged_and_enums_are_sanitized():
    normalized = normalize_setting_value(
        "kiosk_layout",
        {
            "header": {
                "align": "bogus",
                "logo_size": "2xl",
                "show_logo": False,
            },
            "locked_screen": {
                "content_align": "center",
                "pairing_position": "floating",
                "logo_position": "hero",
                "hero_logo_size": "massive",
            },
        },
    )

    assert normalized["preset"] == "balanced"
    assert normalized["header"]["align"] == "left"
    assert normalized["header"]["logo_size"] == "2xl"
    assert normalized["header"]["show_logo"] is False
    assert normalized["header"]["show_title"] is True
    assert normalized["locked_screen"]["content_align"] == "center"
    assert normalized["locked_screen"]["pairing_position"] == "bottom"
    assert normalized["locked_screen"]["logo_position"] == "hero"
    assert normalized["locked_screen"]["hero_logo_size"] == "xl"


def test_kiosk_texts_keep_nested_defaults_and_allow_blank_overrides():
    normalized = normalize_setting_value(
        "kiosk_texts",
        {
            "locked_title": "WELCOME",
            "locked_cards": {
                "credits": {
                    "enabled": False,
                    "label": "",
                    "value": "",
                }
            },
        },
    )

    assert normalized["locked_title"] == "WELCOME"
    assert normalized["locked_subtitle"] == "Bitte an der Theke freischalten lassen"
    assert normalized["locked_cards"]["credits"]["enabled"] is False
    assert normalized["locked_cards"]["credits"]["label"] == ""
    assert normalized["locked_cards"]["credits"]["value"] == ""
    assert normalized["locked_cards"]["credits"]["hint"] == "Preis pro Credit"
    assert normalized["locked_cards"]["matchstart"]["enabled"] is True
    assert normalized["locked_cards"]["unlock"]["label"] == "Freischaltung"


def test_customization_bundle_builds_full_normalized_contracts_from_partial_values():
    bundle = build_customization_bundle_from_values(
        {
            "branding": {"cafe_name": "Bullseye Club"},
            "kiosk_layout": {"header": {"show_logo": False}},
            "kiosk_texts": {"locked_cards": {"unlock": {"enabled": False}}},
            "lockscreen_qr": {"enabled": True, "path": "invalid-no-leading-slash"},
            "pricing": {"mode": "unsupported"},
        }
    )

    assert bundle["branding"]["cafe_name"] == "Bullseye Club"
    assert bundle["branding"]["subtitle"] == "Darts & More"
    assert bundle["kioskLayout"]["header"]["show_logo"] is False
    assert bundle["kioskLayout"]["header"]["show_title"] is True
    assert bundle["kioskTexts"]["locked_cards"]["unlock"]["enabled"] is False
    assert bundle["kioskTexts"]["locked_cards"]["credits"]["enabled"] is True
    assert bundle["lockscreenQr"]["enabled"] is True
    assert bundle["lockscreenQr"]["path"] == "/public/leaderboard"
    assert bundle["pricing"]["mode"] == "per_player"


def test_customization_bundle_import_normalizes_frontend_bundle_shape():
    normalized = normalize_customization_bundle(
        {
            "branding": {"cafe_name": "Venue X"},
            "kioskLayout": {
                "header": {"logo_size": "2xl"},
                "locked_screen": {"logo_position": "hero", "hero_logo_size": "bogus"},
            },
            "kioskTexts": {
                "locked_cards": {
                    "matchstart": {"enabled": False, "hint": "Custom hint"}
                }
            },
            "lockscreenQr": {"enabled": True, "path": "/public/custom"},
        }
    )

    assert normalized["branding"]["cafe_name"] == "Venue X"
    assert normalized["kioskLayout"]["header"]["logo_size"] == "2xl"
    assert normalized["kioskLayout"]["locked_screen"]["logo_position"] == "hero"
    assert normalized["kioskLayout"]["locked_screen"]["hero_logo_size"] == "xl"
    assert normalized["kioskTexts"]["locked_cards"]["matchstart"]["enabled"] is False
    assert normalized["kioskTexts"]["locked_cards"]["matchstart"]["hint"] == "Custom hint"
    assert normalized["lockscreenQr"]["path"] == "/public/custom"
    assert normalized["adminTheme"]["palette_id"] == "slate"
