import json
from functools import lru_cache
from pathlib import Path

from app.catalog.schema import Product

CATALOG_PATH = Path(__file__).resolve().parents[2] / "seed" / "catalog.json"


@lru_cache
def load_catalog() -> list[Product]:
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"Catalog not seeded. Run: python -m seed.seed_catalog (expected {CATALOG_PATH})"
        )
    raw = json.loads(CATALOG_PATH.read_text())
    return [Product(**item) for item in raw]


def get_product(product_id: str) -> Product | None:
    for product in load_catalog():
        if product.id == product_id:
            return product
    return None


def query_catalog(
    max_price_paise: int | None = None,
    category: str | None = None,
    keyword: str | None = None,
) -> list[Product]:
    results = load_catalog()
    if max_price_paise is not None:
        results = [p for p in results if p.price_paise <= max_price_paise]
    if category is not None:
        results = [p for p in results if p.category == category]
    if keyword is not None:
        kw = keyword.lower()
        results = [
            p
            for p in results
            if kw in p.name.lower()
            or kw in p.description.lower()
            or kw in p.category.lower()
            or any(kw in v.lower() for v in p.attributes.values())
        ]
    return results
