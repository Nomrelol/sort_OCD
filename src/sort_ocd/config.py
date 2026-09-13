"""
config.py — User configuration manager for sort_OCD.

Design principle: ZERO friction on first run.
- If no config exists, smart defaults are used automatically.
- Ollama is auto-detected; user only needs to configure if they want something else.
- Config is only written when user explicitly changes a setting via `sort-ocd config`.
"""

import json
import os
from typing import Any, Dict, Optional

CONFIG_PATH = os.path.expanduser("~/.sort_ocd_config.json")

# ─── Defaults (work out-of-the-box, no setup required) ───────────────────────
DEFAULTS: Dict[str, Any] = {
    "ai_backend": "auto",       # auto = try ollama first, then openai, then skip
    "ollama_model": "auto",     # auto = pick best available model
    "ollama_vision_model": "auto",
    "ollama_host": "http://localhost:11434",
    "openai_api_key": None,
    "openai_model": "gpt-4o-mini",
    "anthropic_api_key": None,
    "anthropic_model": "claude-3-haiku-20240307",
    "custom_endpoint": None,    # e.g. http://localhost:1234/v1 for LM Studio
    "custom_model": None,
    "default_sort_mode": "ext",
    "watch_sort_mode": "ext",
    "watch_cooldown_seconds": 3,
    "profiles": {},
}


def load() -> Dict[str, Any]:
    """Load config from disk, merging with defaults for any missing keys."""
    config = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                saved = json.load(f)
            config.update(saved)
        except (json.JSONDecodeError, IOError):
            pass  # silently fall back to defaults
    return config


def save(config: Dict[str, Any]) -> None:
    """Persist config to disk. Creates file if it doesn't exist."""
    try:
        with open(CONFIG_PATH, "w") as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        # Non-fatal: user can still use the tool, config just won't persist
        print(f"Warning: Could not save config to {CONFIG_PATH}: {e}")


def get(key: str) -> Any:
    """Get a single config value."""
    return load().get(key, DEFAULTS.get(key))


def set_value(key: str, value: Any) -> None:
    """Set and persist a single config value."""
    config = load()
    config[key] = value
    save(config)


def save_profile(name: str, profile_data: Dict[str, Any]) -> None:
    """Save a named sorting profile (mode + AI rule + backend)."""
    config = load()
    config.setdefault("profiles", {})[name] = profile_data
    save(config)


def get_profile(name: str) -> Optional[Dict[str, Any]]:
    """Retrieve a saved profile by name. Returns None if not found."""
    return load().get("profiles", {}).get(name)


def list_profiles() -> Dict[str, Any]:
    """Return all saved profiles."""
    return load().get("profiles", {})


def delete_profile(name: str) -> bool:
    """Delete a named profile. Returns True if it existed."""
    config = load()
    profiles = config.get("profiles", {})
    if name in profiles:
        del profiles[name]
        config["profiles"] = profiles
        save(config)
        return True
    return False


def detect_ollama_models() -> list:
    """
    Auto-detect available Ollama models without crashing if Ollama isn't running.
    Returns a list of model name strings, or empty list on failure.
    """
    try:
        import ollama
        response = ollama.list()
        # Handle both old dict format and new object format
        models = response.get("models", []) if isinstance(response, dict) else getattr(response, "models", [])
        names = []
        for m in models:
            if isinstance(m, dict):
                names.append(m.get("name", ""))
            else:
                names.append(getattr(m, "name", ""))
        return [n for n in names if n]
    except Exception:
        return []


def pick_best_ollama_model(models: list) -> Optional[str]:
    """
    From a list of available Ollama models, pick the best text model.
    Priority order: llama3 > mistral > gemma > phi > qwen > any
    """
    priority = ["llama3", "mistral", "gemma", "phi", "qwen", "deepseek", "codellama"]
    for preferred in priority:
        for m in models:
            if preferred in m.lower():
                return m
    return models[0] if models else None


def pick_best_vision_model(models: list) -> Optional[str]:
    """Pick the best vision-capable model from available Ollama models."""
    vision_keywords = ["llava", "bakllava", "moondream", "vision"]
    for keyword in vision_keywords:
        for m in models:
            if keyword in m.lower():
                return m
    return None
