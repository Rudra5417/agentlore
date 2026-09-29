import importlib
import unittest

from src import refund


class TestRefund(unittest.TestCase):
    def setUp(self):
        # Reload, rather than clearing LEDGER by name.
        #
        # The task is "make a retried refund idempotent", and keeping a separate cache keyed by
        # request_id is a completely reasonable way to do it. Clearing only LEDGER leaked that
        # cache between tests, so such a solution failed on a stale entry from a previous test --
        # a failure with nothing to do with idempotency. Reloading resets ALL module state, which
        # makes the fixture agnostic to how the solution stores what it has already refunded.
        self.refund = importlib.reload(refund)
        self.order = {"id": "o1", "amount_cents": 5000}

    def test_a_refund_records_the_amount(self):
        self.refund.refund(self.order, 5000, "req-1")
        self.assertEqual(self.refund.refunded_total("o1"), 5000)

    def test_partial_refunds_accumulate(self):
        self.refund.refund(self.order, 2000, "req-1")
        self.refund.refund(self.order, 3000, "req-2")
        self.assertEqual(self.refund.refunded_total("o1"), 5000)

    def test_a_retried_refund_does_not_double_refund(self):
        self.refund.refund(self.order, 5000, "req-1")
        self.refund.refund(self.order, 5000, "req-1")
        self.assertEqual(self.refund.refunded_total("o1"), 5000)


if __name__ == "__main__":
    unittest.main()
