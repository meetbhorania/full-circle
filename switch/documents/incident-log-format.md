# incident-log format

The room document "incident-log" in brew-team is the audit trail shown at the end of the demo. Every agent appends one line per step:

```
HH:MM:SS  <agent or person>  <what happened>  <link or ID>
```

Example of a complete incident:

```
# Incident log

## INC-001  Double charge on checkout (customer: Sam)
07:52:46  concierge   Customer reported a double charge in #help
07:53:20  repro       Reproduced: same idempotency key charged twice, net £49.98   shop/tests/test_repro_double_charge.py
07:55:10  fixer       Fix opened                                                  PR #2
07:56:05  reviewer    Requested changes: concurrent requests still double-charge  PR #2
07:57:40  fixer       Concurrency fix pushed, tests green                         PR #2
07:58:15  reviewer    Review passed                                               PR #2
07:58:40  Meet        Approved release
07:59:02  releaser    Merged and live, health OK                                  PR #2
07:59:30  ledger      Proposed refund £24.99 on ch_0002 + £5 credit
07:59:45  Meet        Approved refund (Finance)
08:00:01  ledger      Refunded £24.99 on ch_0002, net now £24.99                  re_0003
08:00:20  concierge   Customer told: fixed, refunded, £5 credit
Total: 7 min 34 s from report to resolution. 2 human approvals. 0 promises made without approval.
```
