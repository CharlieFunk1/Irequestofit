"""Equipment categories and items requiring Plastanium Ingots or Spice Melange.

Data sourced from: https://www.magicstark.cz/en/dune-awakening-wiki/

Format: "Item Name": (plastanium_cost, spice_cost)
"""

EQUIPMENT = {
    "Armor Sets": {
        # The Forge Set (Light Armor)
        "The Forge Boots": (40, 53),
        "The Forge Pants": (60, 74),
        "The Forge Gloves": (35, 41),
        "The Forge Helmet": (50, 62),
        "The Forge Chestpiece": (65, 83),
        # Bulwark Set (Heavy Armor)
        "Bulwark Boots": (40, 53),       # Estimated based on pattern
        "Bulwark Leggings": (60, 74),    # Estimated based on pattern
        "Bulwark Gloves": (35, 41),      # Estimated based on pattern
        "Bulwark Helmet": (50, 62),
        "Bulwark Chest": (65, 83),
        # Executor's Set (Heavy Armor)
        "Executor's Boots": (40, 53),    # Estimated based on pattern
        "Executor's Pants": (60, 74),    # Estimated based on pattern
        "Executor's Gloves": (35, 41),   # Estimated based on pattern
        "Executor's Helmet": (50, 62),
        "Executor's Chestpiece": (65, 83),
    },
    "Individual Armor": {
        "Circuit Gauntlets": (35, 41),   # Estimated (gloves pattern)
        "Power Harness": (65, 83),
        "Desert Garb": (45, 83),
        "Hook-claw Gloves": (35, 41),    # Estimated (gloves pattern)
        "Yueh's Reaper Gloves": (35, 41),# Estimated (gloves pattern)
        "Fortress Chestpiece": (65, 83), # Estimated (chest pattern)
        "Seeker Helmet": (50, 62),       # Estimated (helmet pattern)
        "Wayfinder Helm": (50, 62),      # Estimated (helmet pattern)
        "Ix-core Leggings": (60, 74),    # Estimated (legs pattern)
        "Tabr Softstep Boots": (30, 53),
        "Adrenal Boots": (40, 53),       # Estimated (boots pattern)
        "Idaho's Charge": (45, 83),
        "The Baron's Bloodbag": (55, 83),# Estimated (utility pattern)
    },
    "Vehicle Components": {
        # Standard Buggy Mk6 Parts (estimates based on similar items)
        "Buggy Booster Mk6": (80, 120),
        "Buggy Chassis Mk6": (100, 150),
        "Buggy Engine Mk6": (100, 150),
        "Buggy PSU Mk6": (80, 120),
        "Buggy Hull Mk6": (100, 150),
        "Buggy Storage Mk6": (80, 120),
        "Buggy Rear Mk6": (60, 90),
        "Buggy Tread Mk6": (60, 90),
        "Buggy Cutteray Mk6": (100, 150),
        "Buggy Rocket Launcher Mk6": (120, 180),
        # Unique Vehicle Parts
        "Rattler Boost Module": (80, 120),
        "Bluddshot Buggy Engine": (100, 186),
        "Focused Buggy Cutteray": (130, 162),
    },
    "Tools": {
        "Impure Extractor Mk6": (55, 83),
        "Filter Extractor Mk6": (55, 83),
    },
    "Weapons": {
        # Add weapons here: "Weapon Name": (plastanium, spice),
    },
    "Shields": {
        # Add shields here: "Shield Name": (plastanium, spice),
    },
}

CATEGORIES = list(EQUIPMENT.keys())


def get_items_for_category(category: str) -> list[str]:
    """Get all item names for a given category."""
    items = EQUIPMENT.get(category, {})
    return list(items.keys())


def get_item_costs(category: str, item_name: str) -> tuple[int, int]:
    """Get (plastanium, spice) costs for an item. Returns (0, 0) if not found."""
    items = EQUIPMENT.get(category, {})
    return items.get(item_name, (0, 0))
