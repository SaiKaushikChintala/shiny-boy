from dataclasses import dataclass


@dataclass(frozen=True)
class BotOptions:
    name: str
    choices: tuple[str, ...] = ()
    choice_label: str = ""
    choices_as_buttons: bool = True
    has_nature: bool = True
    saves_first: bool = False
    supports_targets: bool = False
    lists_in_worker: bool = False
    advances_from_boot: bool = True
    target_level: str = "—"
    rows_note: str = ""
