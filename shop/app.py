"""Brew & Co: a tiny coffee shop used as the demo target for Full Circle.

Run:  uvicorn shop.app:app --reload --port 8000
Then: open http://localhost:8000

The shop has ONE planted bug for the agents to find and fix. See
docs/the-bug.md (spoilers) if you are a human judge.
"""

from __future__ import annotations

import threading
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


class RefundRequest(BaseModel):
    charge_id: str
    amount_pence: int = Field(gt=0)
    reason: str = Field(min_length=1)
    approved_by: str = Field(min_length=1)


_orders: dict[str, dict] = {}

# Idempotency: one result per idempotency_key. A per-key lock makes a
# concurrent second submit wait for the first and reuse its result instead
# of charging again. Each entry keeps the request it answered, so a key
# reused for a different request gets 409. (Locks are never evicted; fine
# for this demo, a real shop would expire old keys.)
_by_key: dict[str, tuple[tuple, dict]] = {}
_key_locks: dict[str, threading.Lock] = {}
_state_lock = threading.Lock()
_last_order_no = 0


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

    key = req.idempotency_key
    if key is None:
        return _place_order(req, product)

    request = (req.customer, req.item, req.quantity)
    with _state_lock:
        key_lock = _key_locks.setdefault(key, threading.Lock())
    with key_lock:
        if key in _by_key:
            seen, result = _by_key[key]
            if seen != request:
                raise _key_conflict()
            return result

        # After a restart the in-memory map is empty, but the persistent
        # ledger still knows which keys were charged.
        charge = next((c for c in ledger.charges if c.idempotency_key == key), None)
        if charge is not None:
            amount = product["price_pence"] * req.quantity
            if (charge.customer, charge.amount_pence) != (req.customer, amount):
                raise _key_conflict()
            order = _orders.get(charge.order_id) or {
                "order_id": charge.order_id,
                "customer": charge.customer,
                "item": req.item,
                "quantity": req.quantity,
                "amount_pence": charge.amount_pence,
                "charge_id": charge.id,
            }
            return {"order": order, "charge": charge.to_dict()}

        result = _place_order(req, product)
        _by_key[key] = (request, result)
        return result


def _key_conflict() -> HTTPException:
    return HTTPException(
        status_code=409,
        detail="idempotency key reused with a different request",
    )


def _place_order(req: CheckoutRequest, product: dict) -> dict:
    global _last_order_no
    amount = product["price_pence"] * req.quantity
    with _state_lock:
        # Taken under a lock so requests in flight never share an order id.
        _last_order_no = max(_last_order_no, ledger.order_count()) + 1
        order_id = f"ord_{_last_order_no:04d}"

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


@app.post("/api/_reset")
def reset() -> dict:
    """Demo helper for humans only: wipe orders and the ledger before a take.

    Agents must never call this. It destroys customers' payment records.
    """
    global _last_order_no
    with _state_lock:
        _orders.clear()
        _by_key.clear()
        _key_locks.clear()
        _last_order_no = 0
    ledger.reset()
    return {"ok": True}
