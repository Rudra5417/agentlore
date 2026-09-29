"""The inbound HTTP layer."""
from . import errors, refund


def handle_refund(payload, request_id):
    """`request_id` is chosen by the client and is stable across its retries."""
    try:
        return refund.refund(payload["order"], payload["amount_cents"], request_id)
    except errors.RefundError as exc:
        return {"status": 400, "code": exc.code}
