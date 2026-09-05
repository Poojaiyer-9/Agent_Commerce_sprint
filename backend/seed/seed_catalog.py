"""Populates a small synthetic merchant catalog for the demo.

Run with: python -m seed.seed_catalog
Writes backend/seed/catalog.json, which app/catalog/store.py loads at startup.
"""
import json
from pathlib import Path

CATALOG = [
    {
        "id": "bag-classic-black",
        "name": "Classic Black Laptop Bag",
        "description": "14-inch padded laptop bag with a shoulder strap and two side pockets.",
        "price_paise": 129900,
        "currency": "INR",
        "stock": 42,
        "category": "bags",
        "attributes": {"fits_up_to": "15.6 inch", "material": "polyester", "color": "black"},
        "upsell_ids": ["sleeve-neoprene-13"],
        "image_url": None,
    },
    {
        "id": "bag-canvas-brown",
        "name": "Canvas Messenger Bag",
        "description": "Retro-style canvas messenger bag, water-resistant lining.",
        "price_paise": 149900,
        "currency": "INR",
        "stock": 25,
        "category": "bags",
        "attributes": {"fits_up_to": "14 inch", "material": "canvas", "color": "brown"},
        "upsell_ids": ["sleeve-neoprene-13"],
        "image_url": None,
    },
    {
        "id": "bag-compact-grey",
        "name": "Compact Commuter Bag",
        "description": "Slim laptop bag for 13-inch laptops, minimalist design.",
        "price_paise": 99900,
        "currency": "INR",
        "stock": 60,
        "category": "bags",
        "attributes": {"fits_up_to": "13 inch", "material": "nylon", "color": "grey"},
        "upsell_ids": ["mouse-wireless-compact"],
        "image_url": None,
    },
    {
        "id": "sleeve-neoprene-13",
        "name": "Neoprene Laptop Sleeve (13-inch)",
        "description": "Shock-absorbing neoprene sleeve, fits inside most laptop bags.",
        "price_paise": 39900,
        "currency": "INR",
        "stock": 80,
        "category": "accessories",
        "attributes": {"fits_up_to": "13 inch", "material": "neoprene"},
        "upsell_ids": [],
        "image_url": None,
    },
    {
        "id": "mouse-wireless-compact",
        "name": "Compact Wireless Mouse",
        "description": "Silent-click wireless mouse, USB-C rechargeable.",
        "price_paise": 79900,
        "currency": "INR",
        "stock": 100,
        "category": "accessories",
        "attributes": {"connectivity": "wireless", "battery": "rechargeable"},
        "upsell_ids": [],
        "image_url": None,
    },
    {
        "id": "charger-65w-gan",
        "name": "65W GaN Fast Charger",
        "description": "Compact dual-port GaN charger for laptops and phones.",
        "price_paise": 249900,
        "currency": "INR",
        "stock": 35,
        "category": "accessories",
        "attributes": {"wattage": "65W", "ports": "2"},
        "upsell_ids": [],
        "image_url": None,
    },
    {
        "id": "backpack-travel-25l",
        "name": "Travel Backpack 25L",
        "description": "Anti-theft travel backpack with a dedicated 15-inch laptop compartment.",
        "price_paise": 189900,
        "currency": "INR",
        "stock": 18,
        "category": "bags",
        "attributes": {"fits_up_to": "15 inch", "capacity": "25L", "color": "navy"},
        "upsell_ids": ["mouse-wireless-compact", "charger-65w-gan"],
        "image_url": None,
    },
    {
        "id": "stand-aluminum-laptop",
        "name": "Aluminum Laptop Stand",
        "description": "Adjustable ergonomic laptop stand, foldable for travel.",
        "price_paise": 109900,
        "currency": "INR",
        "stock": 50,
        "category": "accessories",
        "attributes": {"material": "aluminum", "adjustable": "yes"},
        "upsell_ids": [],
        "image_url": None,
    },
    {
        "id": "keyboard-compact-bt",
        "name": "Compact Bluetooth Keyboard",
        "description": "Slim multi-device Bluetooth keyboard with scissor-switch keys.",
        "price_paise": 159900,
        "currency": "INR",
        "stock": 44,
        "category": "accessories",
        "attributes": {"connectivity": "bluetooth", "layout": "compact"},
        "upsell_ids": [],
        "image_url": None,
    },
    {
        "id": "hub-usbc-7in1",
        "name": "USB-C Hub (7-in-1)",
        "description": "7-in-1 USB-C hub with HDMI, SD card reader and 3 USB-A ports.",
        "price_paise": 189900,
        "currency": "INR",
        "stock": 30,
        "category": "accessories",
        "attributes": {"ports": "7-in-1", "output": "HDMI 4K"},
        "upsell_ids": [],
        "image_url": None,
    },
    {
        "id": "bag-premium-leather",
        "name": "Premium Leather Briefcase",
        "description": "Full-grain leather briefcase with a padded 15-inch laptop sleeve.",
        "price_paise": 499900,
        "currency": "INR",
        "stock": 8,
        "category": "bags",
        "attributes": {"fits_up_to": "15 inch", "material": "leather", "color": "tan"},
        "upsell_ids": ["mouse-wireless-compact"],
        "image_url": None,
    },
    {
        "id": "lock-cable-security",
        "name": "Laptop Cable Lock",
        "description": "Combination cable lock for securing a laptop to a desk.",
        "price_paise": 59900,
        "currency": "INR",
        "stock": 70,
        "category": "accessories",
        "attributes": {"type": "combination"},
        "upsell_ids": [],
        "image_url": None,
    },
]


def main() -> None:
    out_path = Path(__file__).parent / "catalog.json"
    out_path.write_text(json.dumps(CATALOG, indent=2))
    print(f"Seeded {len(CATALOG)} products to {out_path}")


if __name__ == "__main__":
    main()
