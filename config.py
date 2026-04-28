import os
import toml

DEFAULT_CONFIG = {
    "pronounce": {
        "enabled": True,
        "loop": 1,
        "delay": 1.0,
    },
}


def load_config():
    config_path = os.path.join(os.path.dirname(__file__), "config.toml")
    if os.path.exists(config_path):
        try:
            data = toml.load(config_path)
            merged = DEFAULT_CONFIG.copy()
            for section, values in data.items():
                if section in merged and isinstance(values, dict):
                    merged[section].update(values)
                else:
                    merged[section] = values
            return merged
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()
