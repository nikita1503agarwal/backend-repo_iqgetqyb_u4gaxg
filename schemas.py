"""
Database Schemas for NeoPencil

Each Pydantic model represents a collection in MongoDB. The collection name is the lowercase of the class name.
"""

from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True
    role: Literal["user", "admin"] = "user"


class Product(BaseModel):
    slug: str = Field(..., description="Unique product slug")
    title: str
    description: str
    base_price: float = Field(..., ge=0)
    colors: List[str] = Field(default_factory=lambda: ["Graphite", "Neon Blue", "Aurora Green", "Solar Orange"]) 
    textures: List[str] = Field(default_factory=lambda: ["matte", "gloss", "carbon"]) 
    features: List[str] = Field(default_factory=lambda: ["digital-sync", "tilt-sense", "haptic-feedback"]) 
    images: List[str] = Field(default_factory=list)
    in_stock: bool = True
    inventory: int = 100


class CartItem(BaseModel):
    user_id: str
    product_id: str
    quantity: int = Field(1, ge=1)
    color: Optional[str] = None
    texture: Optional[str] = None
    selected_features: List[str] = Field(default_factory=list)
    unit_price: float = Field(..., ge=0)


class Order(BaseModel):
    user_id: str
    items: List[Dict]  # store snapshot of items
    total_amount: float
    status: Literal["pending", "paid", "shipped", "delivered", "cancelled"] = "pending"
    subscription_id: Optional[str] = None
    shipping_address: Optional[Dict] = None
    payment_ref: Optional[str] = None


class Subscription(BaseModel):
    user_id: str
    product_id: str
    plan: Literal["monthly", "quarterly", "yearly"] = "monthly"
    status: Literal["active", "paused", "cancelled"] = "active"
    refill_quantity: int = Field(2, ge=1)


class InventoryEvent(BaseModel):
    product_id: str
    delta: int
    reason: Literal["order", "restock", "adjust"] = "order"
