"""Mock payments provider for the Brew & Co demo shop.

Keeps an in-memory ledger of charges and refunds so the double charge
(and the refund that fixes it) is visible at GET /api/charges.

Nothing here touches real money.
"""

from __future__ import annotations

import itertools
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class Charge:
    id: str
    order_id: str
    customer: str
    amount_pence: int
    idempotency_key: str | None
    created_at: str
    refunded_pence: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Refund:
    id: str
    charge_id: str
    amount_pence: int
    reason: str
    approved_by: str
    created_at: str


@dataclass
class Ledger:
    charges: list[Charge] = field(default_factory=list)
    refunds: list[Refund] = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def _next(self, prefix: str) -> str:
        return f"{prefix}_{next(self._ids):04d}"

    def charge(
        self,
        order_id: str,
        customer: str,
        amount_pence: int,
        idempotency_key: str | None = None,
    ) -> Charge:
        """Take a payment.

        The provider records the idempotency key it is given but does not
        de-duplicate on it. De-duplication is the shop's job.

        Like a real card network, it takes a moment to answer
        (PAYMENT_LATENCY_MS, default 800 ms).
        """
        time.sleep(int(os.environ.get("PAYMENT_LATENCY_MS", "800")) / 1000)
        with self._lock:
            c = Charge(
                id=self._next("ch"),
                order_id=order_id,
                customer=customer,
                amount_pence=amount_pence,
                idempotency_key=idempotency_key,
                created_at=_now(),
            )
            self.charges.append(c)
            return c

    def refund(self, charge_id: str, amount_pence: int, reason: str, approved_by: str) -> Refund:
        with self._lock:
            charge = next((c for c in self.charges if c.id == charge_id), None)
            if charge is None:
                raise KeyError(f"unknown charge {charge_id}")
            remaining = charge.amount_pence - charge.refunded_pence
            if amount_pence <= 0 or amount_pence > remaining:
                raise ValueError(f"refund must be between 1 and {remaining} pence")
            charge.refunded_pence += amount_pence
            r = Refund(
                id=self._next("re"),
                charge_id=charge_id,
                amount_pence=amount_pence,
                reason=reason,
                approved_by=approved_by,
                created_at=_now(),
            )
            self.refunds.append(r)
            return r

    def reset(self) -> None:
        with self._lock:
            self.charges.clear()
            self.refunds.clear()
            self._ids = itertools.count(1)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


ledger = Ledger()
