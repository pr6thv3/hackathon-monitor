"""Unit tests for configuration loading and preferences."""

from src.config import load_config, AppConfig, PreferenceProfile


def test_load_default_config():
    """Verify default configuration loading from config.yaml."""
    cfg = load_config("config.yaml")
    assert isinstance(cfg, AppConfig)
    assert cfg.user_name == "Preethve"
    assert len(cfg.portals) >= 1
    assert cfg.portals[0].id == "vit_eventhub"
    assert "hackathon" in cfg.preference_profile.wanted_event_types or len(cfg.preference_profile.topics) > 0


def test_load_missing_config_fallback():
    """Verify fallback to defaults if non-existent file path is provided."""
    cfg = load_config("non_existent_config.yaml")
    assert isinstance(cfg, AppConfig)
    assert cfg.user_name == "Builder"
