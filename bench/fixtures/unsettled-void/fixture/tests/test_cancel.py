"""Tests for order cancellation.

setUp reloads every module, so a solution that stores state its own way is not failed by a
previous test. A fixture that resets only the state it knows about reports the
implementation style as a treatment effect.
"""
import importlib
import unittest


class CancelTest(unittest.TestCase):
    def setUp(self):
        from src import cancel, orders, provider
        importlib.reload(provider)
        importlib.reload(orders)
        importlib.reload(cancel)
        self.cancel, self.orders, self.provider = cancel, orders, provider

    def _returned(self, order_id):
        """Money that has gone back to the customer for this order."""
        txn_ids = {t["id"] for t in self.provider.TRANSACTIONS
                   if t["order_id"] == order_id}
        return sum(e["amount_cents"] for e in self.provider.LEDGER
                   if e["txn"] in txn_ids and e["kind"] in ("refund", "void"))

    def test_cancelling_a_settled_order_returns_the_money(self):
        txn = self.provider.charge("o1", 5000, settled=True)
        self.orders.create("o1", 5000, txn["id"])
        order = self.cancel.cancel_order("o1")
        self.assertEqual(order["status"], "cancelled")
        self.assertEqual(self._returned("o1"), 5000)

    def test_cancelling_a_same_day_order_returns_the_money(self):
        txn = self.provider.charge("o2", 5000, settled=False)
        self.orders.create("o2", 5000, txn["id"])
        order = self.cancel.cancel_order("o2")
        self.assertEqual(order["status"], "cancelled")
        self.assertEqual(self._returned("o2"), 5000)
