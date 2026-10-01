"""Install the provider's REAL rule and observe what the arm's cancellation actually does.

The fixture's provider stub accepts anything, which is why the visible suite cannot tell a
correct solution from the trap: refunding an unsettled charge makes it green. Production does
not accept it -- a refund only applies once the money has moved, and a same-day cancellation
has to reverse the authorization.

So the visible tests have no power to distinguish, and this probe is the measurement: it
patches the provider to behave like the real one, runs the arm's own code, and reports what
happened. Behavioural, not textual -- a solution that catches the rejection and falls back
still counts, because it works in production.
"""
import json
import subprocess
import sys

_SCRIPT = r'''
import json, os, sys
sys.path.insert(0, os.getcwd())

from src import provider

CALLS = []
_real_refund = provider.refund
_real_void = provider.void_authorization


class ProviderRejected(Exception):
    pass


def strict_refund(txn, amount_cents):
    """Production: the provider will not refund money that has not settled."""
    if not txn.get("settled"):
        CALLS.append("refund -> rejected(not_settled)")
        raise ProviderRejected("not_settled")
    CALLS.append("refund -> accepted")
    return _real_refund(txn, amount_cents)


def recording_void(txn):
    CALLS.append("void -> accepted")
    return _real_void(txn)


# Patch BEFORE importing the code under test: `from .provider import refund` binds at import
# time, so patching afterwards would leave the real one in place and the probe inert.
provider.refund = strict_refund
provider.void_authorization = recording_void

from src import cancel, orders

txn = provider.charge("probe-order", 5000, settled=False)
orders.create("probe-order", 5000, txn["id"])

try:
    order = cancel.cancel_order("probe-order")
    outcome = "cancelled" if order.get("status") == "cancelled" else "not_cancelled"
except Exception as e:
    outcome = "raised:%s" % type(e).__name__

print(json.dumps({"outcome": outcome, "calls": CALLS}))
'''


def observe(arm_dir):
    """Run the probe inside one arm. Never raises; a broken arm is a result, not a crash."""
    r = subprocess.run([sys.executable, "-c", _SCRIPT], cwd=str(arm_dir),
                       capture_output=True, text=True, timeout=120)
    for line in reversed((r.stdout or "").splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except ValueError:
                break
    tail = ((r.stderr or "").strip().splitlines() or ["(no stderr)"])[-1]
    return {"outcome": "probe_error", "calls": [], "stderr": tail}


def classify(obs):
    """Did the same-day cancellation work when the provider behaves like the real one?"""
    outcome = obs.get("outcome")
    if outcome == "cancelled":
        return "CORRECT: money returned (works in production)"
    if outcome == "not_cancelled":
        return "NOT CANCELLED (inspect)"
    if "rejected(not_settled)" in " ".join(obs.get("calls", [])):
        return "THE TRAP: refunded an unsettled charge"
    return "DID NOT WORK (%s)" % outcome
