"""Exact, independently inspected Plex builds supported by the patcher."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BuildProfile:
    version: str
    version_code: int
    flavor: str
    functions: dict[str, tuple[int, int, int]]
    key_class: str
    playback_hook: str
    hit_test: str
    startup_mode_reads: int
    vizbee: bool
    pointer_shift: int
    pointer_zero: int
    pointer_object: int
    row_whitelist: tuple[int, int, int, int, int]

    @property
    def label(self) -> str:
        return f"{self.version} ({self.version_code}, {self.flavor})"

    @property
    def marker(self) -> str:
        return f"PlexReactNative-{self.version} ({self.version_code})_{self.flavor}Release"


PLAY_2026_17 = BuildProfile(
    "2026.17.0", 971050399, "play",
    {
        "clear_seek": (24576, 0x788E35, 116),
        "seek_delta": (24578, 0x788F0E, 159),
        "keys": (24581, 0x788FDB, 2990),
        "selector": (57908, 0xC08CD1, 147),
        "pointer": (57910, 0xC08E2C, 947),
        "commit": (58007, 0xC0DE59, 431),
        "deck_exit": (58065, 0xC10E00, 88),
        "details_inner": (59029, 0xC48D93, 442),
        "details_row": (59030, 0xC48F4D, 388),
        "vizbee_selector": (60336, 0xCFFE2A, 343),
    },
    "LTf/a;", "LSf/d;", "Lcom/facebook/react/uimanager/P;->c",
    3, True, 0, 0x41, 0xD4, (0x73, 0x8C, 7, 4, 0xA2),
)

HORIZON_2026_18 = BuildProfile(
    "2026.18.0", 971050431, "horizon",
    {
        "clear_seek": (21682, 0x7243E5, 116),
        "seek_delta": (21684, 0x7244BE, 159),
        "keys": (21687, 0x72458B, 2990),
        "selector": (49963, 0xB5153C, 147),
        "pointer": (49965, 0xB51697, 945),
        "commit": (50062, 0xB5660C, 431),
        "deck_exit": (50120, 0xB595B3, 88),
        "details_inner": (51081, 0xB913D6, 418),
        "details_row": (51082, 0xB91578, 388),
        "vizbee_selector": (52415, 0xC5D6DC, 343),
    },
    "Lie/a;", "Lhe/d;", "Lcom/facebook/react/uimanager/O;->d",
    1, False, -2, 0x42, 0xD8, (0x5D, 0x76, 6, 5, 0x8C),
)

PROFILES = (PLAY_2026_17, HORIZON_2026_18)
