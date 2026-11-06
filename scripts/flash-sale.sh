#!/usr/bin/env bash
# Simulate Brew & Co's one-hour beans flash sale against the live shop.
#
#   ./scripts/flash-sale.sh
#
# 30 customers check out, one at a time. The payment provider is slow
# (~0.8 s), so 13 of them double-tap "Pay now": two requests with the same
# idempotency key arrive while the first is still processing. With the bug,
# each of those 13 is charged twice. Nobody complains... until Sam does.
#
# Run it after ./scripts/reset-demo.sh and before Sam pays in the browser.
# All customers are made up. Needs only bash and curl.
set -euo pipefail
SHOP="${SHOP_URL:-http://localhost:8000}"

curl -sf "$SHOP/api/health" >/dev/null || { echo "Shop isn't answering at $SHOP"; exit 1; }

# name|item|quantity|double-tap?
ORDERS=(
  "Priya Shah|beans-1kg|1|yes"
  "Tom Reed|flat-white|1|no"
  "Amara Okafor|beans-1kg|2|yes"
  "Leo Martin|oat-latte|1|no"
  "Hannah Cole|beans-1kg|1|no"
  "Raj Patel|beans-1kg|1|yes"
  "Chloe Evans|flat-white|2|no"
  "Daniel Kim|beans-1kg|1|yes"
  "Fatima Ali|beans-1kg|1|no"
  "Owen Price|oat-latte|2|yes"
  "Grace Liu|beans-1kg|1|no"
  "Ben Taylor|beans-1kg|1|yes"
  "Sofia Rossi|flat-white|1|no"
  "Kwame Mensah|beans-1kg|1|yes"
  "Emily Clarke|beans-1kg|1|no"
  "Arjun Mehta|beans-1kg|2|yes"
  "Lucy Ward|oat-latte|1|no"
  "Noah Green|beans-1kg|1|no"
  "Zara Hussain|beans-1kg|1|yes"
  "Jack Wilson|flat-white|1|no"
  "Mei Chen|beans-1kg|1|yes"
  "Oliver Brown|beans-1kg|1|no"
  "Isla Murphy|oat-latte|1|no"
  "Ravi Kumar|beans-1kg|1|yes"
  "Ella Davies|beans-1kg|1|no"
  "Sean Okoro|flat-white|1|no"
  "Nina Petrova|beans-1kg|1|yes"
  "Harry Scott|beans-1kg|1|no"
  "Aiden Lee|oat-latte|1|no"
  "Maya Singh|beans-1kg|1|yes"
)

pay() {  # customer item quantity key
  curl -s -o /dev/null -X POST "$SHOP/api/checkout" -H 'content-type: application/json' \
    -d "{\"customer\":\"$1\",\"item\":\"$2\",\"quantity\":$3,\"idempotency_key\":\"$4\"}"
}

echo "☕ Brew & Co flash sale: ${#ORDERS[@]} customers checking out…"
n=0; taps=0
for o in "${ORDERS[@]}"; do
  IFS='|' read -r name item qty double <<<"$o"
  key="sale-$(date +%s%N)-$RANDOM"
  if [ "$double" = yes ]; then
    pay "$name" "$item" "$qty" "$key" & sleep 0.2; pay "$name" "$item" "$qty" "$key" & wait
    taps=$((taps + 1)); mark="👆👆"
  else
    pay "$name" "$item" "$qty" "$key"; mark="👆"
  fi
  n=$((n + 1)); printf '  %2d. %-14s %-10s x%s %s\n' "$n" "$name" "$item" "$qty" "$mark"
done

curl -s "$SHOP/api/charges" | python3 -c "
import json, sys
from collections import defaultdict
d = json.load(sys.stdin); by = defaultdict(list)
for c in d['charges']: by[c['idempotency_key']].append(c)
dup = [cs for cs in by.values() if len(cs) > 1]
extra = sum(c['amount_pence'] for cs in dup for c in cs[1:])
print()
print(f'Done. {len(d[\"charges\"])} charges in the ledger.')
print(f'Hidden damage: {len(dup)} customers charged twice, £{extra/100:.2f} taken that should not have been.')
print('Nobody has complained yet. Now Sam double-taps Pay in the browser and writes to @concierge.')
"
