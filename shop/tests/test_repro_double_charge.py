"""Repro: one checkout attempt (same idempotency_key) is charged twice.

Two submits of the same attempt, e.g. a double click on Pay while the
payment provider is still answering, each create a charge. The shop never
de-duplicates on idempotency_key. Test data is made up.

Fails on current code; passes once checkout is idempotent per key.
"""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from shop.app import app

client = TestClient(app)
ORDER = {"customer": "Test Customer", "item": "beans-1kg", "idempotency_key": "test-key-0001"}


@pytest.fixture(autouse=True)
def clean():
    client.post("/api/_reset")  # resets the per-run temporary ledger (see conftest.py)
    yield


def test_retry_with_same_idempotency_key_charges_once():
    first = client.post("/api/checkout", json=ORDER)
    second = client.post("/api/checkout", json=ORDER)
    assert first.status_code == 200 and second.status_code == 200

    ledger = client.get("/api/charges").json()
    assert len(ledger["charges"]) == 1, ledger
    assert ledger["net_pence"] == 2499
    assert second.json()["charge"]["id"] == first.json()["charge"]["id"]


def test_concurrent_double_submit_charges_once(monkeypatch):
    monkeypatch.setenv("PAYMENT_LATENCY_MS", "300")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post("/api/checkout", json=ORDER), range(2)))
    assert all(r.status_code == 200 for r in results)

    ledger = client.get("/api/charges").json()
    assert len(ledger["charges"]) == 1, ledger
    assert ledger["net_pence"] == 2499


def test_reused_key_with_different_request_returns_409():
    first = client.post("/api/checkout", json=ORDER)
    assert first.status_code == 200
    changed = client.post("/api/checkout", json={**ORDER, "quantity": 3})
    assert changed.status_code == 409, changed.json()

    ledger = client.get("/api/charges").json()
    assert len(ledger["charges"]) == 1, ledger
    assert ledger["net_pence"] == 2499


def test_different_keys_in_flight_get_distinct_orders(monkeypatch):
    monkeypatch.setenv("PAYMENT_LATENCY_MS", "300")
    orders = [{**ORDER, "idempotency_key": f"test-key-1{i:03d}"} for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda o: client.post("/api/checkout", json=o), orders))
    assert all(r.status_code == 200 for r in results)
    assert len({r.json()["order"]["order_id"] for r in results}) == 2
