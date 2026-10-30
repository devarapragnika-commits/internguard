"""Checks for the payment detector. Does not call the network."""

import inspect
import unittest

import backend.services.payment as payment
from backend.services.payment import FINANCIAL_REQUEST_CAP, detect_payment_request

POLITE_FEE = (
    "Dear candidate, we are pleased to inform you that you have been selected. "
    "Kindly pay the registration fee of Rs 2000 at your convenience to confirm your place."
)

UNPAID_OFFER = (
    "We are pleased to offer you an unpaid software internship. "
    "There is no registration fee and no deposit. "
    "The stipend is Rs 15000 per month, paid at the end of each month. "
    "A laptop will be provided. You do not need to buy one."
)


class PaymentDetectorTests(unittest.TestCase):
    def test_fee_language_raises_financial_risk_by_itself(self):
        result = detect_payment_request(POLITE_FEE)
        self.assertTrue(result["flagged"])
        self.assertEqual(result["flag"], "financial_request")
        self.assertEqual(result["financial_request_risk"], FINANCIAL_REQUEST_CAP)
        self.assertEqual(result["financial_request_cap"], 25)
        self.assertIn("registration fee", result["reason"])
        self.assertNotIn("act now", POLITE_FEE.lower())

    def test_reason_names_each_kind_of_request(self):
        samples = {
            "Please pay the training fee before the course starts.": "training fee",
            "An upfront deposit is required to hold your seat.": "upfront deposit",
            "Buy a Google Play gift card and send us the code.": "gift card",
            "You can complete the payment in bitcoin.": "bitcoin payment",
            "Pay 500 to receive the offer letter.": "payment to receive the offer letter",
            "Pay the charges to release the laptop.": "payment to release the laptop",
        }
        for text, kind in samples.items():
            result = detect_payment_request(text)
            self.assertEqual(result["financial_request_risk"], 25, text)
            self.assertIn(kind, result["requests"], text)
            self.assertIn(kind, result["reason"], text)

    def test_unpaid_offer_stays_at_zero(self):
        result = detect_payment_request(UNPAID_OFFER)
        self.assertFalse(result["flagged"])
        self.assertEqual(result["flag"], "")
        self.assertEqual(result["reason"], "")
        self.assertEqual(result["requests"], [])
        self.assertEqual(result["financial_request_risk"], 0)
        self.assertEqual(result["financial_request_cap"], 25)

    def test_negated_fee_does_not_score(self):
        result = detect_payment_request("There is no registration fee and no security deposit.")
        self.assertEqual(result["financial_request_risk"], 0)
        self.assertEqual(result["reason"], "")

    def test_empty_text_does_not_crash(self):
        for text in ("", "   ", None, "hello", 123):
            result = detect_payment_request(text)
            self.assertEqual(result["financial_request_risk"], 0)
            self.assertFalse(result["flagged"])

    def test_same_text_is_stable(self):
        self.assertEqual(
            detect_payment_request(POLITE_FEE),
            detect_payment_request(POLITE_FEE),
        )

    def test_does_not_use_the_linguistic_detector(self):
        source = inspect.getsource(payment)
        self.assertNotIn("linguistic", source)
        self.assertNotIn("extract_linguistic", source)


if __name__ == "__main__":
    unittest.main()
