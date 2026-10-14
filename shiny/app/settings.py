import json

from shiny.paths import SETTINGS_PATH

RECENT_ROM_COUNT = 8


class Settings:
    def __init__(self) -> None:
        self.volume = 100
        self.muted = False
        self.recent: list[str] = []
        self.cheats: dict[str, dict] = {}
        try:
            stored = json.loads(SETTINGS_PATH.read_text())
            self.volume = max(0, min(100, int(stored.get("volume", 100))))
            self.muted = bool(stored.get("muted", False))
            self.recent = [path for path in stored.get("recent", []) if isinstance(path, str)][:RECENT_ROM_COUNT]
            self.cheats = {
                game: entry for game, entry in stored.get("cheats", {}).items() if isinstance(entry, dict) and isinstance(entry.get("text"), str)
            }
        except (OSError, ValueError, AttributeError):
            pass

    def save(self) -> None:
        try:
            SETTINGS_PATH.write_text(json.dumps({"volume": self.volume, "muted": self.muted, "recent": self.recent, "cheats": self.cheats}))
        except OSError as error:
            print(f"Could not save settings: {error}")

    def remember_rom(self, path: str) -> None:
        self.recent = [path] + [other for other in self.recent if other != path]
        del self.recent[RECENT_ROM_COUNT:]
