"""Client for the payment provider.

In production this talks to the provider's HTTP API. Here it is an in-memory fake so the
test suite runs offline.
"""
from . import errors

LEDGER = []
TRANSACTIONS = []
_seq = [0]


def charge(order_id, amount_cents, settled=True):
    """Take a payment for an order.

    Real charges settle in the provider's nightly batch. Until then the money has not
    moved, and the transaction is an authorization.
    """
    _seq[0] += 1
    txn = {
        "id": "txn_%04d" % _seq[0],
        "order_id": order_id,
        "amount_cents": amount_cents,
        "settled": settled,
    }
    TRANSACTIONS.append(txn)
    LEDGER.append({"kind": "charge", "txn": txn["id"], "amount_cents": amount_cents})
    return txn


def lookup_transaction(txn_id):
    for t in TRANSACTIONS:
        if t["id"] == txn_id:
            return t
    raise errors.BillingError("unknown transaction %s" % txn_id)


def refund(txn, amount_cents):
    """Send money back to the card the customer paid with."""
    LEDGER.append({"kind": "refund", "txn": txn["id"], "amount_cents": amount_cents})
    return {"txn": txn["id"], "amount_cents": amount_cents}


def void_authorization(txn):
    """Reverse an authorization with the provider."""
    LEDGER.append({"kind": "void", "txn": txn["id"], "amount_cents": txn["amount_cents"]})
    return {"txn": txn["id"], "amount_cents": txn["amount_cents"]}
