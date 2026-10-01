"""Checkout: take payment for an order."""
from . import orders, provider


def checkout(order_id, amount_cents):
    """Charge the customer and record the order."""
    txn = provider.charge(order_id, amount_cents)
    if amount_cents <= 0:
        # Nothing was ever owed, so release the hold rather than leave it open.
        provider.void_authorization(txn)
        raise ValueError("invalid amount for order %s" % order_id)
    return orders.create(order_id, amount_cents, txn["id"])
