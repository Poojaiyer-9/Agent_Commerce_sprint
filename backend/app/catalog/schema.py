from pydantic import BaseModel, Field


class Product(BaseModel):
    """Agent-readable catalog entry.

    Prices are in paise (INR * 100) throughout the system to avoid
    floating-point money bugs and to match Razorpay's API units directly.
    """

    id: str
    name: str
    description: str
    price_paise: int = Field(gt=0)
    currency: str = "INR"
    stock: int = Field(ge=0)
    category: str
    attributes: dict[str, str] = Field(default_factory=dict)
    upsell_ids: list[str] = Field(default_factory=list)
    image_url: str | None = None

    @property
    def price_rupees(self) -> float:
        return self.price_paise / 100
