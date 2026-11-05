"""Happy-path tests for Brew & Co.

These pass on the shipped code. They deliberately do NOT cover retries:
writing the test that exposes the double charge is the Repro agent's job.
"""

import pytest
from fastapi.testclient import TestClient

from shop.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean():
    client.post("/api/_reset")
    yield


def test_health():
    assert client.get("/api/health").json() == {"ok": True}


def test_checkout_charges_the_right_amount():
    r = client.post("/api/checkout", json={"customer": "Sam", "item": "oat-latte", "quantity": 2})
    assert r.status_code == 200
    assert r.json()["charge"]["amount_pence"] == 790


def test_two_different_orders_make_two_charges():
    client.post("/api/checkout", json={"customer": "Sam", "item": "flat-white", "idempotency_key": "a"})
    client.post("/api/checkout", json={"customer": "Sam", "item": "flat-white", "idempotency_key": "b"})
    assert len(client.get("/api/charges").json()["charges"]) == 2


def test_unknown_item_is_rejected():
    r = client.post("/api/checkout", json={"customer": "Sam", "item": "tea"})
    assert r.status_code == 404


def test_refund_reduces_net():
    ch = client.post("/api/checkout", json={"customer": "Sam", "item": "beans-1kg"}).json()["charge"]
    r = client.post("/api/refunds", json={
        "charge_id": ch["id"], "amount_pence": 2499, "reason": "test", "approved_by": "finance",
    })
    assert r.status_code == 200
    assert client.get("/api/charges").json()["net_pence"] == 0


def test_cannot_over_refund():
    ch = client.post("/api/checkout", json={"customer": "Sam", "item": "flat-white"}).json()["charge"]
    r = client.post("/api/refunds", json={
        "charge_id": ch["id"], "amount_pence": 9999, "reason": "test", "approved_by": "finance",
    })
    assert r.status_code == 400
