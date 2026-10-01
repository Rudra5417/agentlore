"""Order cancellation."""
from . import errors, orders, provider


def cancel_order(order_id):
    """Cancel an order and return the customer's money."""
    order = orders.get(order_id)
    txn = provider.lookup_transaction(order["transaction_id"])
    if not txn["settled"]:
        # TODO: same-day cancellations are not handled yet.
        raise errors.Unsupported("cannot cancel order %s yet" % order_id)
    provider.refund(txn, order["amount_cents"])
    order["status"] = "cancelled"
    return order
