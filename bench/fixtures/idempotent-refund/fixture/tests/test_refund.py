import unittest

from src import refund


class TestRefund(unittest.TestCase):
    def setUp(self):
        refund.LEDGER.clear()
        self.order = {"id": "o1", "amount_cents": 5000}

    def test_a_refund_records_the_amount(self):
        refund.refund(self.order, 5000, "req-1")
        self.assertEqual(refund.refunded_total("o1"), 5000)

    def test_partial_refunds_accumulate(self):
        refund.refund(self.order, 2000, "req-1")
        refund.refund(self.order, 3000, "req-2")
        self.assertEqual(refund.refunded_total("o1"), 5000)

    def test_a_retried_refund_does_not_double_refund(self):
        refund.refund(self.order, 5000, "req-1")
        refund.refund(self.order, 5000, "req-1")
        self.assertEqual(refund.refunded_total("o1"), 5000)


if __name__ == "__main__":
    unittest.main()
