"""Repro: one checkout attempt (same idempotency_key) charges the card twice.

Customer Sam was charged 2 x 350p for one flat white on 2026-11-05 ~09:32 UTC.
Live ledger showed ch_0001 and ch_0002: same order_id, same idempotency_key,
same second. The shop never de-duplicates on idempotency_key.

Fails on current code; passes once checkout is idempotent per key.
"""

import os
from concurrent.futures import ThreadPoolExecutor

os.environ.setdefault("PAYMENT_LATENCY_MS", "0")

import pytest
from fastapi.testclient import TestClient

from shop.app import app

client = TestClient(app)
ORDER = {"customer": "Sam", "item": "flat-white", "idempotency_key": "2d07d12d-same-attempt"}


@pytest.fixture(autouse=True)
def clean():
    client.post("/api/_reset")
    yield


def test_retry_with_same_idempotency_key_charges_once():
    first = client.post("/api/checkout", json=ORDER)
    second = client.post("/api/checkout", json=ORDER)  # e.g. browser retry
    assert first.status_code == 200 and second.status_code == 200

    ledger = client.get("/api/charges").json()
    assert len(ledger["charges"]) == 1, ledger
    assert ledger["net_pence"] == 350
    assert second.json()["charge"]["id"] == first.json()["charge"]["id"]


def test_concurrent_double_submit_charges_once(monkeypatch):
    # Real-world shape of Sam's case: two requests in flight at once
    # while the payment provider takes its time to answer.
    monkeypatch.setenv("PAYMENT_LATENCY_MS", "300")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post("/api/checkout", json=ORDER), range(2)))
    assert all(r.status_code == 200 for r in results)

    ledger = client.get("/api/charges").json()
    assert len(ledger["charges"]) == 1, ledger
    assert ledger["net_pence"] == 350
