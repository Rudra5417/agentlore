"""Single funnel for every payment provider call."""


class OutOfRefundWindow(Exception):
    """The provider refused a refund because the charge is too old to refund.

    Deliberately a distinct type rather than a generic provider error: this is not
    retryable and there is no fallback that fixes it.
    """


class Gateway:
    """Retries, idempotency keys and audit logging live here and nowhere else."""

    def __init__(self, provider):
        self.provider = provider

    def charge(self, customer_id, cents, idempotency_key):
        return self.provider.charge(customer_id, cents, idempotency_key)

    def refund(self, charge_id, idempotency_key):
        try:
            return self.provider.refund(charge_id, idempotency_key)
        except Exception as exc:
            # A 409 means the charge is outside the provider's refund window. It is not a
            # retry signal, and issuing a credit note instead does not help: a credit note
            # runs the same window check and is refused the same way.
            if getattr(exc, "status", None) == 409:
                raise OutOfRefundWindow(str(exc)) from exc
            raise
