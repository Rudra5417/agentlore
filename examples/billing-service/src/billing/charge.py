"""Billing entrypoints. All provider traffic goes through Gateway."""
import uuid

from .gateway import Gateway


def charge(gateway: Gateway, customer_id, cents):
    # idempotency key generated once, here, so retries are safe
    return gateway.charge(customer_id, cents, uuid.uuid4().hex)
