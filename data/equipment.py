"""Equipment categories and items requiring Plastanium Ingots or Spice Melange."""

EQUIPMENT = {
    "Armor Sets": [
        "The Forge Boots",
        "The Forge Pants",
        "The Forge Gloves",
        "The Forge Helmet",
        "The Forge Chestpiece",
        "Bulwark Boots",
        "Bulwark Leggings",
        "Bulwark Gloves",
        "Bulwark Helmet",
        "Bulwark Chest",
        "Executor's Boots",
        "Executor's Pants",
    ],
    "Individual Armor": [
        "Circuit Gauntlets",
        "Power Harness",
        "Desert Garb",
        "Hook-claw Gloves",
        "Yueh's Reaper Gloves",
        "Fortress Chestpiece",
        "Seeker Helmet",
        "Wayfinder Helm",
        "Ix-core Leggings",
        "Tabr Softstep Boots",
        "Adrenal Boots",
        "Idaho's Charge",
        "The Baron's Bloodbag",
    ],
    "Vehicle Components": [
        "Buggy Booster Mk6",
        "Buggy Chassis Mk6",
        "Buggy Engine Mk6",
        "Buggy PSU Mk6",
        "Buggy Hull Mk6",
        "Buggy Storage Mk6",
        "Buggy Rear Mk6",
        "Buggy Tread Mk6",
        "Buggy Cutteray Mk6",
        "Buggy Rocket Launcher Mk6",
        "Rattler Boost Module",
        "Bluddshot Buggy Engine",
        "Focused Buggy Cutteray",
    ],
    "Tools": [
        "Impure Extractor Mk6",
        "Filter Extractor Mk6",
    ],
}

CATEGORIES = list(EQUIPMENT.keys())


def get_items_for_category(category: str) -> list[str]:
    """Get all items for a given category."""
    return EQUIPMENT.get(category, [])
