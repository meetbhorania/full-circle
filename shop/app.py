"""Brew & Co: a tiny coffee shop used as the demo target for Full Circle.

Run:  uvicorn shop.app:app --reload --port 8000
Then: open http://localhost:8000

The shop has ONE planted bug for the agents to find and fix. See
docs/the-bug.md (spoilers) if you are a human judge.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from shop.payments import ledger

STATIC = Path(__file__).parent / "static"

MENU = {
    "flat-white": {"name": "Flat White", "price_pence": 350},
    "oat-latte": {"name": "Oat Latte", "price_pence": 395},
    "beans-1kg": {"name": "House Beans 1kg", "price_pence": 2499},
}

app = FastAPI(title="Brew & Co", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class CheckoutRequest(BaseModel):
    customer: str = Field(min_length=1, max_length=80)
    item: str
    quantity: int = Field(default=1, ge=1, le=20)
    idempotency_key: str | None = Field(
        default=None,
        description="Sent by the checkout page, one per checkout attempt.",
    )


class CreditRequest(BaseModel):
    customer: str = Field(min_length=1, max_length=80)
    amount_pence: int = Field(gt=0)
    reason: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)


class RefundRequest(BaseModel):
    charge_id: str
    amount_pence: int = Field(gt=0)
    reason: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)


_orders: dict[str, dict] = {}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/menu")
def menu() -> dict:
    return MENU


@app.post("/api/checkout")
def checkout(req: CheckoutRequest) -> dict:
    product = MENU.get(req.item)
    if product is None:
        raise HTTPException(status_code=404, detail=f"unknown item {req.item}")

    amount = product["price_pence"] * req.quantity
    order_id = f"ord_{ledger.order_count() + 1:04d}"

    charge = ledger.charge(
        order_id=order_id,
        customer=req.customer,
        amount_pence=amount,
        idempotency_key=req.idempotency_key,
    )
    _orders[order_id] = {
        "order_id": order_id,
        "customer": req.customer,
        "item": req.item,
        "quantity": req.quantity,
        "amount_pence": amount,
        "charge_id": charge.id,
    }
    return {"order": _orders[order_id], "charge": charge.to_dict()}


@app.get("/api/charges")
def charges() -> dict:
    """The payments ledger. Agents read this to spot and prove a double charge."""
    return {
        "charges": [c.to_dict() for c in ledger.charges],
        "refunds": [r.to_dict() for r in ledger.refunds],
        "credits": [c.to_dict() for c in ledger.credits],
        "net_pence": sum(c.amount_pence - c.refunded_pence for c in ledger.charges),
    }


@app.post("/api/refunds")
def refund(req: RefundRequest) -> dict:
    try:
        r = ledger.refund(req.charge_id, req.amount_pence, req.reason, req.approved_by)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"refund": r.to_dict()}


@app.post("/api/credits")
def credit(req: CreditRequest) -> dict:
    """Goodwill credit on the customer's next order (refund policy rule 2)."""
    try:
        c = ledger.credit(req.customer, req.amount_pence, req.reason, req.approved_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"credit": c.to_dict()}


@app.post("/api/_reset")
def reset() -> dict:
    """Demo helper for humans only: wipe orders and the ledger before a take.

    Agents must never call this. It destroys customers' payment records.
    """
    _orders.clear()
    ledger.reset()
    return {"ok": True}
