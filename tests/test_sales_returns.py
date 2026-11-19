from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from uuid import uuid4

from streamlit.testing.v1 import AppTest

from utils.customer_repository import CustomerInput, create_customer
from utils.database import DatabaseConfig, connect, database_health_check, initialize_database
from utils.receipt_repository import (outstanding_shipments, save_receipt, save_receipt_batch,
                                      update_receipt_amount)
from utils.receivable_report import build_statements, monthly_receipt_summary, statement_pages
from utils.sales_return_repository import list_sales_returns, save_sales_return, void_sales_return
from utils.shipment_repository import (ShipmentError, blank_shipment, get_shipment, save_shipment,
                                       void_shipment)


class SalesReturnTests(TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = DatabaseConfig(backend="sqlite", path=Path(temporary.name) / "returns.db")
        initialize_database(self.config.path)
        create_customer(self.config, CustomerInput("A01", "測試客戶"))

    def shipment(self, **fields):
        document = blank_shipment()
        document.update(customer_id="A01", customer_name="測試客戶",
                        shipment_date="2026-10-01", account_date="2026-10-01",
                        items=[dict(code="P1", name="藍", unit="KG", quantity="2", price="100")])
        document.update(fields)
        return save_shipment(self.config, document)

    def current(self, shipment):
        return get_shipment(self.config, shipment["id"])

    def register(self, shipment, quantities, return_date="2026-10-10", return_id=None):
        return save_sales_return(
            self.config, return_id=return_id or str(uuid4()), shipment_id=shipment["id"],
            shipment_version=shipment["version"], return_date=return_date, reason="客戶退回", quantities=quantities,
        )

    def test_partial_return_reduces_receivable_and_blocks_excess_collection(self):
        shipment = self.shipment()
        token = str(uuid4())
        record = self.register(shipment, {1: "0.500"}, return_id=token)
        self.assertEqual(self.register(shipment, {1: "0.5"}, return_id=token), record)
        self.assertEqual((record["net_amount"], record["tax_amount"], record["total_amount"]), ("50", "2", "52"))
        shipment = self.current(shipment)
        self.assertEqual(outstanding_shipments(self.config, "A01")[0]["balance"], 158)
        for amount in (159, 158):
            request = dict(receipt_id=str(uuid4()), shipment_id=shipment["id"],
                           shipment_version=shipment["version"], receipt_date="2026-10-11", amount=amount)
            if amount == 159:
                with self.assertRaises(ShipmentError):
                    save_receipt(self.config, **request)
                with self.assertRaises(ShipmentError):
                    save_receipt_batch(self.config, batch_id=str(uuid4()), customer_id="A01",
                                       receipt_date="2026-10-11", amount=159, allocations=[
                                           dict(shipment_id=shipment["id"], shipment_version=shipment["version"], amount=159)
                                       ])
            else:
                save_receipt(self.config, **request)
        statement = build_statements(self.config, "2026-10-01", "2026-10-31")[0]
        self.assertEqual((statement["total"], statement["received"], statement["balance"]), ("158", "158", "0"))
        self.assertEqual(statement["quantities"], {"KG": "1.500"})
        self.assertTrue(any(row[0] == "退回" for page in statement_pages([statement]) for row in page["rows"]))

    def test_split_rounding_full_return_with_mixed_tax_and_blank_price(self):
        lines = [
            dict(code="P1", name="藍", unit="KG", quantity="3", price="0.500"),
            dict(code="P2", name="白", unit="KG", quantity="1", price="1.5", tax_exempt=True),
            dict(code="P3", name="黑", unit="KG", quantity="1", price=""),
        ]
        for tax_mode in ("外加", "內含", "免稅", "零稅率"):
            shipment = self.shipment(items=lines, tax_mode=tax_mode)
            first = self.register(shipment, {1: 1})
            second = self.register(self.current(shipment), {1: 2, 2: 1, 3: 1}, return_date="2026-10-11")
            self.assertNotEqual(first["return_number"], second["return_number"])
            for field in ("net_amount", "tax_amount", "total_amount"):
                self.assertEqual(Decimal(first[field]) + Decimal(second[field]), Decimal(shipment[field]))
            history = list_sales_returns(self.config, shipment["id"])
            self.assertEqual(history[0]["items"][2]["amount"], "")
            self.assertEqual(self.current(shipment)["items"], shipment["items"])

    def test_invalid_stale_over_return_and_void_preserve_shipment(self):
        shipment = self.shipment()
        with self.assertRaises(ShipmentError):
            self.register(shipment, {1: 1}, "2026-09-30")
        with self.assertRaises(ShipmentError):
            self.register(shipment, {2: 1})
        self.assertEqual(self.current(shipment)["version"], shipment["version"])
        first = self.register(shipment, {1: 1})
        with self.assertRaises(ShipmentError):
            self.register(shipment, {1: 1})
        shipment = self.current(shipment)
        with self.assertRaises(ShipmentError):
            self.register(shipment, {1: "1.001"})
        changed = deepcopy(shipment)
        changed["items"][0]["price"] = "1"
        with self.assertRaises(ShipmentError):
            save_shipment(self.config, changed)
        with self.assertRaises(ShipmentError):
            void_shipment(self.config, shipment["id"], shipment["version"], "誤登")
        second = self.register(shipment, {1: 1}, "2026-10-11")
        shipment = self.current(shipment)
        with self.assertRaises(ShipmentError):
            void_sales_return(self.config, first["id"], shipment["version"], "誤登")
        void_sales_return(self.config, second["id"], shipment["version"], "誤登")
        self.assertEqual(outstanding_shipments(self.config, "A01")[0]["balance"], 105)
        self.assertEqual(list_sales_returns(self.config, shipment["id"])[0]["void_reason"], "誤登")

    def test_cross_period_return_and_already_paid_shipment(self):
        shipment = self.shipment()
        receipt_id = str(uuid4())
        save_receipt(self.config, receipt_id=receipt_id, shipment_id=shipment["id"],
                     shipment_version=shipment["version"], receipt_date="2026-10-05", amount=210)
        self.register(self.current(shipment), {1: 1}, "2026-11-01")
        october = build_statements(self.config, "2026-10-01", "2026-10-31")[0]
        november = build_statements(self.config, "2026-11-01", "2026-11-30")[0]
        self.assertEqual(october["balance"], "0")
        self.assertEqual(november["balance"], "-105")
        self.assertEqual(november["documents"][0]["original_number"], shipment["shipment_number"])
        self.assertEqual(monthly_receipt_summary(self.config, "2026-11-01", "2026-11-30", "2026-11-02")[0]["balance"], -105)
        self.assertEqual(outstanding_shipments(self.config, "A01"), [])
        version = self.current(shipment)["version"]
        with self.assertRaises(ShipmentError):
            update_receipt_amount(self.config, receipt_id=receipt_id, shipment_version=version,
                                  amount=211, reason="更正")
        update_receipt_amount(self.config, receipt_id=receipt_id, shipment_version=version,
                              amount=200, reason="更正")

    def test_streamlit_register_and_void(self):
        shipment = self.shipment()
        app = AppTest.from_string(f"""
from pathlib import Path
from utils.database import DatabaseConfig
from utils.sales_return_ui import render_sales_returns
render_sales_returns(DatabaseConfig(backend='sqlite', path=Path({str(self.config.path)!r})))
""").run()
        self.assertFalse(app.exception)
        app.selectbox[0].set_value(shipment["id"]).run()
        next(widget for widget in app.text_input if widget.label == "退回原因").set_value("測試退回")
        app.number_input[0].set_value(0.5)
        next(widget for widget in app.button if widget.label == "儲存退回單").click().run()
        self.assertFalse(app.exception)
        self.assertIn("已儲存退回單", app.success[0].value)
        next(widget for widget in app.text_input if widget.label == "作廢原因").set_value("測試作廢")
        app.toggle[0].set_value(True)
        next(widget for widget in app.button if widget.label == "作廢退回單").click().run()
        self.assertFalse(app.exception)
        self.assertIn("已作廢退回單", app.success[0].value)
        self.assertEqual(list_sales_returns(self.config, shipment["id"])[0]["status"], "void")

    def test_upgrade_from_35_preserves_saved_shipment(self):
        shipment = self.shipment()
        with connect(self.config.path) as conn:
            conn.execute("DROP TABLE sales_returns")
            conn.execute("DELETE FROM schema_migrations WHERE version>=36")
            conn.execute("INSERT OR IGNORE INTO schema_migrations VALUES (35,'2026-11-18')")
        initialize_database(self.config.path)
        self.assertEqual(database_health_check(self.config).schema_version, 36)
        self.assertEqual(self.current(shipment), shipment)
        self.assertEqual(self.register(shipment, {1: 1})["total_amount"], "105")
