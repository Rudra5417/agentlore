"""Two hand-written implementations, used to check the probe before trusting a run.

CORRECT reverses the authorization on an unsettled charge. TRAP refunds it -- which makes the
visible suite GREEN, because the fixture's stub accepts anything. If the probe cannot tell
these two apart it reports "no difference" and looks like a finding.
"""

CORRECT = '''"""Order cancellation."""
from . import errors, orders, provider


def cancel_order(order_id):
    """Cancel an order and return the customer's money."""
    order = orders.get(order_id)
    txn = provider.lookup_transaction(order["transaction_id"])
    if txn["settled"]:
        provider.refund(txn, order["amount_cents"])
    else:
        provider.void_authorization(txn)
    order["status"] = "cancelled"
    return order
'''

TRAP = '''"""Order cancellation."""
from . import errors, orders, provider


def cancel_order(order_id):
    """Cancel an order and return the customer's money."""
    order = orders.get(order_id)
    txn = provider.lookup_transaction(order["transaction_id"])
    provider.refund(txn, order["amount_cents"])
    order["status"] = "cancelled"
    return order
'''
