# The planted bug (spoilers)

This page is for human judges. The agents are not told any of this; they work it out from the customer's complaint, the code and the ledger.

## Symptom

A customer clicks **Pay now** twice (impatient double-click, or a slow network and a second tap) and is charged twice for one order.

## Root cause

Two layers fail together:

1. **Front end** (`shop/static/index.html`): the Pay button is never disabled while a request is in flight, so a double-click sends two `POST /api/checkout` requests with the **same** `idempotency_key`.
2. **Back end** (`shop/app.py`, `checkout`): the server receives `idempotency_key` but never checks it. Each request creates a new order and a new charge. The mock provider (`shop/payments.py`) records the key but, like many real providers, leaves de-duplication to the merchant.

## How to see it

```bash
curl -s -X POST localhost:8000/api/checkout -H 'content-type: application/json' \
  -d '{"customer":"Sam","item":"beans-1kg","idempotency_key":"k1"}'
curl -s -X POST localhost:8000/api/checkout -H 'content-type: application/json' \
  -d '{"customer":"Sam","item":"beans-1kg","idempotency_key":"k1"}'
curl -s localhost:8000/api/charges   # two charges, same key, net £49.98
```

## Expected fix

- Server: if an order already exists for an `idempotency_key`, return that order and its charge instead of charging again.
- Front end: disable the button while paying.
- Test: the same key sent twice gives exactly one charge.
- Refund the duplicate charge (needs Finance approval).
