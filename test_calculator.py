import io
import json
import unittest

from app import UtilityHandler
from calculator import CalculationError, calculate_utilities


class CalculatorTests(unittest.TestCase):
    def test_standard_proportional_calculation(self):
        result = calculate_utilities({
            "period": "Ноябрь 2026",
            # Свет: Настя Толя = 150, Алёна Айрат = 100 (всего 250 -> 60% и 40%), счёт 1000 -> 600 и 400
            "elec_h1_prev": "1000",
            "elec_h1_curr": "1150",
            "elec_h2_prev": "500",
            "elec_h2_curr": "600",
            "elec_bill": "1000",
            # Газ: Дом А = 25, Дом Б = 75 (всего 100 -> 25% и 75%), счёт 400 -> 100 и 300
            "gas_h1_prev": "200",
            "gas_h1_curr": "225",
            "gas_h2_prev": "300",
            "gas_h2_curr": "375",
            "gas_bill": "400",
            # Вода: 60 -> по 30, Мусор: 20 -> по 10
            "water_bill": "60",
            "trash_bill": "20",
        })

        self.assertEqual(result["house1_name"], "Настя Толя")
        self.assertEqual(result["house2_name"], "Алёна Айрат")
        self.assertEqual(result["electricity"]["house1"]["diff"], "150")
        self.assertEqual(result["electricity"]["house2"]["diff"], "100")
        self.assertEqual(result["electricity"]["house1"]["cost"], "600.00")
        self.assertEqual(result["electricity"]["house2"]["cost"], "400.00")

        self.assertEqual(result["gas"]["house1"]["cost"], "100.00")
        self.assertEqual(result["gas"]["house2"]["cost"], "300.00")

        self.assertEqual(result["water"]["house1_cost"], "30.00")
        self.assertEqual(result["trash"]["house1_cost"], "10.00")

        # Дом А: 600 + 100 + 30 + 10 = 740.00
        # Дом Б: 400 + 300 + 30 + 10 = 740.00
        self.assertEqual(result["totals"]["house1"], "740.00")
        self.assertEqual(result["totals"]["house2"], "740.00")
        self.assertEqual(result["totals"]["bills_total"], "1480.00")

    def test_comma_decimals_and_empty_fields(self):
        result = calculate_utilities({
            "elec_h1_prev": "10,5",
            "elec_h1_curr": "20,5",
            "elec_h2_prev": "0",
            "elec_h2_curr": "30",
            "elec_bill": "100,40 ₾",
            "gas_h1_prev": "",
            "gas_h1_curr": "",
            "gas_h2_prev": "",
            "gas_h2_curr": "",
            "gas_bill": "",
            "water_bill": "15,50 ₾",
            "trash_bill": "",
        })
        # Свет: 10 и 30 (25% и 75% от 100.40 -> 25.10 и 75.30)
        self.assertEqual(result["electricity"]["house1"]["cost"], "25.10")
        self.assertEqual(result["electricity"]["house2"]["cost"], "75.30")
        # Вода: 15.50 / 2 = 7.75
        self.assertEqual(result["water"]["house1_cost"], "7.75")
        self.assertEqual(result["totals"]["house1"], "32.85")
        self.assertEqual(result["totals"]["house2"], "83.05")

    def test_zero_usage_with_bill_splits_equally(self):
        result = calculate_utilities({
            "gas_h1_prev": "500",
            "gas_h1_curr": "500",
            "gas_h2_prev": "700",
            "gas_h2_curr": "700",
            "gas_bill": "50",
        })
        self.assertEqual(result["gas"]["house1"]["cost"], "25.00")
        self.assertEqual(result["gas"]["house2"]["cost"], "25.00")
        self.assertTrue(result["gas"]["note"])

    def test_curr_less_than_prev_raises_error(self):
        with self.assertRaises(CalculationError):
            calculate_utilities({
                "elec_h1_prev": "200",
                "elec_h1_curr": "190",
                "elec_bill": "100",
            })

    def test_negative_value_raises_error(self):
        with self.assertRaises(CalculationError):
            calculate_utilities({
                "water_bill": "-10",
            })


class _MockSocket:
    def __init__(self, raw_request: bytes):
        self._rfile = io.BytesIO(raw_request)
        self.wfile = io.BytesIO()

    def makefile(self, mode: str, *args, **kwargs):
        return self._rfile if "r" in mode else self.wfile

    def sendall(self, data: bytes):
        self.wfile.write(data)


class HttpHandlerTests(unittest.TestCase):
    def _send_raw(self, raw_request: bytes) -> bytes:
        sock = _MockSocket(raw_request)
        UtilityHandler(sock, ("127.0.0.1", 12345), None)
        return sock.wfile.getvalue()

    def test_get_index_html(self):
        resp = self._send_raw(b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n").decode("utf-8")
        self.assertIn("200 OK", resp)
        self.assertIn("Расчёт коммунальных платежей", resp)

    def test_post_calculate_api(self):
        body = json.dumps({
            "elec_h1_prev": "100",
            "elec_h1_curr": "120",
            "elec_h2_prev": "200",
            "elec_h2_curr": "260",
            "elec_bill": "80",
            "water_bill": "20",
        }).encode("utf-8")
        req = (
            f"POST /api/calculate HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n\r\n"
        ).encode("utf-8") + body
        resp = self._send_raw(req).decode("utf-8")
        self.assertIn("200 OK", resp)
        json_part = resp.split("\r\n\r\n", 1)[1]
        data = json.loads(json_part)
        self.assertEqual(data["totals"]["house1"], "30.00")
        self.assertEqual(data["totals"]["house2"], "70.00")


if __name__ == "__main__":
    unittest.main()
