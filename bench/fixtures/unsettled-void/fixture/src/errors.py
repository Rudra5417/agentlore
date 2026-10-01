"""Errors raised by the billing service."""


class BillingError(Exception):
    """Base class for billing failures."""


class Unsupported(BillingError):
    """The service cannot do this yet."""


class ProviderRejected(BillingError):
    """The provider refused the request."""
