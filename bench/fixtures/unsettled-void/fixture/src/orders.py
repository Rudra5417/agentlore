"""In-memory order store."""
ORDERS = {}


def create(order_id, amount_cents, txn_id, status="paid"):
    ORDERS[order_id] = {
        "id": order_id,
        "amount_cents": amount_cents,
        "transaction_id": txn_id,
        "status": status,
    }
    return ORDERS[order_id]


def get(order_id):
    return ORDERS[order_id]
