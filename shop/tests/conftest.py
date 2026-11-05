"""Loaded by pytest before any test file.

Every test run gets its own temporary ledger and no payment delay, so tests
can never touch the live shop's ledger (shop/data/ledger.json).
"""

import os
import tempfile

os.environ["LEDGER_PATH"] = os.path.join(tempfile.mkdtemp(), "ledger.json")
os.environ.setdefault("PAYMENT_LATENCY_MS", "0")
