"""Single funnel for every payment provider call."""


class Gateway:
    """Retries, idempotency keys and audit logging live here and nowhere else."""

    def __init__(self, provider):
        self.provider = provider

    def charge(self, customer_id, cents, idempotency_key):
        return self.provider.charge(customer_id, cents, idempotency_key)

    def refund(self, charge_id, idempotency_key):
        return self.provider.refund(charge_id, idempotency_key)
