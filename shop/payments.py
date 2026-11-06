"""Mock payments provider for the Brew & Co demo shop.

Keeps a ledger of charges and refunds so the double charge (and the refund
that fixes it) is visible at GET /api/charges. The ledger is saved to a JSON
file (LEDGER_PATH, default shop/data/ledger.json), so it survives the shop
restarting after a deploy.

Nothing here touches real money.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path(__file__).parent / "data" / "ledger.json"


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

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Credit:
    id: str
    customer: str
    amount_pence: int
    reason: str
    approved_by: str
    created_at: str

    def to_dict(self) -> dict:
        return asdict(self)


class Ledger:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or os.environ.get("LEDGER_PATH", DEFAULT_PATH))
        self._lock = threading.Lock()
        self.charges: list[Charge] = []
        self.refunds: list[Refund] = []
        self.credits: list[Credit] = []
        self._seq = 0
        self._load()

    # --- persistence -----------------------------------------------------
    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text() or "{}")
        self.charges = [Charge(**c) for c in data.get("charges", [])]
        self.refunds = [Refund(**r) for r in data.get("refunds", [])]
        self.credits = [Credit(**c) for c in data.get("credits", [])]
        self._seq = data.get("seq", 0)

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "seq": self._seq,
            "charges": [c.to_dict() for c in self.charges],
            "refunds": [r.to_dict() for r in self.refunds],
            "credits": [c.to_dict() for c in self.credits],
        }, indent=2))
        tmp.replace(self.path)

    def _next(self, prefix: str) -> str:
        self._seq += 1
        return f"{prefix}_{self._seq:04d}"

    # --- reads -----------------------------------------------------------
    def order_count(self) -> int:
        """How many distinct orders have been charged so far."""
        with self._lock:
            return len({c.order_id for c in self.charges})

    # --- writes ----------------------------------------------------------
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
            self._save()
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
            self._save()
            return r

    def credit(self, customer: str, amount_pence: int, reason: str, approved_by: str) -> Credit:
        """Goodwill credit on a customer's next order."""
        with self._lock:
            if amount_pence <= 0 or amount_pence > 2000:
                raise ValueError("credit must be between 1 and 2000 pence")
            c = Credit(
                id=self._next("cr"),
                customer=customer,
                amount_pence=amount_pence,
                reason=reason,
                approved_by=approved_by,
                created_at=_now(),
            )
            self.credits.append(c)
            self._save()
            return c

    def reset(self) -> None:
        with self._lock:
            self.charges.clear()
            self.refunds.clear()
            self.credits.clear()
            self._seq = 0
            self._save()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


ledger = Ledger()
