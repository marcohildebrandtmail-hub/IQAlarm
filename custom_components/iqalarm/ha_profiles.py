"""Stable native HA controls select IQAlarm profiles, never their alarm policy."""

HA_PROFILE_MODES = ("armed_home", "armed_night", "armed_away", "armed_vacation")
HA_CUSTOM_MODE = "armed_custom_bypass"
HA_DEFAULT_NAMES = ("Besuch", "Nacht", "Abwesend", "Urlaub")


def initial_ha_profiles(profiles) -> dict[str, str]:
    """Associate existing profiles once; later renaming/reordering keeps these IDs."""
    result = {}
    for mode, name in zip(HA_PROFILE_MODES, HA_DEFAULT_NAMES, strict=True):
        # Existing Besuch profiles may have a user-generated ID alongside Zuhause.
        named = next((key for key, profile in profiles.items() if profile.name == name), None)
        key = (
            named
            if mode == "armed_home" and named is not None
            else mode
            if mode in profiles
            else named
        )
        if key is not None and key not in result.values():
            result[mode] = key
    return result
