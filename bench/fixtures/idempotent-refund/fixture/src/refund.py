"""Refund handling for the billing service."""
from . import errors

# Every refund we have recorded, in the order we recorded them.
LEDGER = []


def refund(order, amount_cents, request_id):
    """Refund `amount_cents` of `order` and return the refund record.

    Not idempotent yet: a retried call records a second refund.
    """
    record = {
        "order_id": order["id"],
        "amount_cents": amount_cents,
        "request_id": request_id,
    }
    LEDGER.append(record)
    return record


def refunded_total(order_id):
    return sum(r["amount_cents"] for r in LEDGER if r["order_id"] == order_id)
