"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user"
- Product -> "product"
- Coupon -> "coupon"
"""

from pydantic import BaseModel, Field
from typing import Optional


class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")


class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")


class Coupon(BaseModel):
    """
    Coupons collection schema
    Collection name: "coupon"
    """
    code: str = Field(..., description="Unique coupon code, e.g., WBAU10DIC-000001")
    channel: Optional[str] = Field("whatsapp", description="Acquisition channel")
    redeemed: bool = Field(False, description="Whether the coupon has been redeemed")
