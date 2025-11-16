import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import User, Product, CartItem, Order, Subscription, InventoryEvent

app = FastAPI(title="NeoPencil API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ObjectIdStr(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return str(v)


@app.get("/")
def read_root():
    return {"message": "NeoPencil backend running"}


@app.get("/api/products", response_model=List[Product])
def list_products():
    products = db.product.find().limit(50)
    return [Product(**{k: v for k, v in p.items() if k != "_id"}) for p in products]


@app.post("/api/products", status_code=201)
def create_product_endpoint(product: Product):
    # Ensure unique slug
    if db.product.find_one({"slug": product.slug}):
        raise HTTPException(status_code=400, detail="Slug already exists")
    create_document("product", product)
    return {"ok": True}


class AddToCart(BaseModel):
    user_id: str
    product_slug: str
    quantity: int = 1
    color: Optional[str] = None
    texture: Optional[str] = None
    selected_features: Optional[List[str]] = None


@app.post("/api/cart/add")
def add_to_cart(body: AddToCart):
    prod = db.product.find_one({"slug": body.product_slug})
    if not prod:
        raise HTTPException(404, "Product not found")
    price = prod.get("base_price", 0.0)
    doc = CartItem(
        user_id=body.user_id,
        product_id=str(prod["_id"]),
        quantity=body.quantity,
        color=body.color,
        texture=body.texture,
        selected_features=body.selected_features or [],
        unit_price=price,
    )
    create_document("cartitem", doc)
    return {"ok": True}


@app.get("/api/cart/{user_id}")
def get_cart(user_id: str):
    items = db.cartitem.find({"user_id": user_id})
    # join product info
    result = []
    for it in items:
        prod = db.product.find_one({"_id": ObjectId(it["product_id"])})
        it["id"] = str(it.pop("_id"))
        if prod:
            it["product"] = {k: v for k, v in prod.items() if k != "_id"}
        result.append(it)
    return result


class CheckoutRequest(BaseModel):
    user_id: str


@app.post("/api/checkout")
def checkout(req: CheckoutRequest):
    items = list(db.cartitem.find({"user_id": req.user_id}))
    if not items:
        raise HTTPException(400, "Cart is empty")

    # compute total and snapshot
    snapshot = []
    total = 0.0
    for it in items:
        total += float(it["unit_price"]) * int(it["quantity"])
        snapshot.append({k: v for k, v in it.items() if k != "_id"})

    order = Order(user_id=req.user_id, items=snapshot, total_amount=total)
    order_id = create_document("order", order)

    # decrement inventory for each product
    for it in items:
        try:
            db.product.update_one(
                {"_id": ObjectId(it["product_id"])},
                {"$inc": {"inventory": -int(it["quantity"])}}
            )
        except Exception:
            pass

    # clear cart
    db.cartitem.delete_many({"user_id": req.user_id})

    return {"ok": True, "order_id": order_id}


class SubscriptionRequest(BaseModel):
    user_id: str
    product_slug: str
    plan: str = "monthly"
    refill_quantity: int = 2


@app.post("/api/subscriptions")
def create_subscription(req: SubscriptionRequest):
    prod = db.product.find_one({"slug": req.product_slug})
    if not prod:
        raise HTTPException(404, "Product not found")
    sub = Subscription(
        user_id=req.user_id,
        product_id=str(prod["_id"]),
        plan=req.plan, refill_quantity=req.refill_quantity
    )
    sub_id = create_document("subscription", sub)
    return {"ok": True, "subscription_id": sub_id}


@app.get("/api/inventory/{slug}")
def get_inventory(slug: str):
    prod = db.product.find_one({"slug": slug})
    if not prod:
        raise HTTPException(404, "Product not found")
    return {"inventory": prod.get("inventory", 0), "in_stock": bool(prod.get("in_stock", True))}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
