"""Error codes the API layer knows how to map to responses."""


class RefundError(Exception):
    code = "refund_error"


class OutOfWindowError(RefundError):
    code = "refund_out_of_window"


class RefundInProgressError(RefundError):
    code = "refund_in_progress"
