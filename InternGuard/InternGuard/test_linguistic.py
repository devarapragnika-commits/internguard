"""Checks for the linguistic feature extractor. Does not call the network."""

import inspect
import unittest

import backend.linguistic as linguistic
from backend.linguistic import LINGUISTIC_SIGNALS, extract_linguistic_features

SCAM = (
    "Act now. This offer is for today only and needs immediate joining. "
    "Pay the registration fee before joining. "
    "Send your bank account number and OTP. "
    "Guaranteed selection. Earn $500 per day. "
    "Do not tell anyone and keep this private."
)

LEGIT = (
    "We are hiring a software engineering intern for a 12-week summer program. "
    "The stipend is ₹25,000 per month, paid after the first month. "
    "There is no registration fee and no deposit. "
    "Apply on our careers page with your resume. "
    "Interviews will be scheduled next week. "
    "You will get coffee on the first day."
)


class LinguisticFeatureTests(unittest.TestCase):
    def test_scam_and_legitimate_offer_differ(self):
        scam = extract_linguistic_features(SCAM)
        legit = extract_linguistic_features(LEGIT)

        self.assertEqual(list(scam), list(LINGUISTIC_SIGNALS))
        for name, feature in scam.items():
            self.assertEqual(feature["value"], 1, name)
            self.assertTrue(feature["reason"], name)
        for name, feature in legit.items():
            self.assertEqual(feature["value"], 0, name)
            self.assertEqual(feature["reason"], "", name)
        self.assertNotEqual(scam, legit)

    def test_same_text_always_returns_the_same_features(self):
        self.assertEqual(
            extract_linguistic_features(SCAM),
            extract_linguistic_features(SCAM),
        )
        self.assertEqual(
            extract_linguistic_features(LEGIT),
            extract_linguistic_features(LEGIT),
        )

    def test_empty_and_short_text_do_not_crash(self):
        for text in ("", "   ", "hi", "ok", "!!!", None):
            features = extract_linguistic_features(text)
            self.assertEqual(list(features), list(LINGUISTIC_SIGNALS))
            for feature in features.values():
                self.assertEqual(feature["value"], 0)
                self.assertEqual(feature["reason"], "")

    def test_issue_phrases(self):
        cases = [
            ("Act now!", "urgency", "act now"),
            ("TODAY ONLY", "urgency", "today only"),
            ("Immediate joining", "urgency", "immediate joining"),
            ("payment before joining", "financial_pressure", "payment before joining"),
            ("Do not tell anyone.", "secrecy", "do not tell anyone"),
            ("keep this private", "secrecy", "keep this private"),
        ]
        for text, signal, phrase in cases:
            features = extract_linguistic_features(text)
            self.assertEqual(features[signal]["value"], 1, text)
            self.assertIn(phrase, features[signal]["reason"], text)
            for other, feature in features.items():
                if other != signal:
                    self.assertEqual(feature["value"], 0, f"{text} also fired {other}")

    def test_each_signal_can_fire_on_its_own(self):
        samples = {
            "urgency": "Please act now.",
            "financial_pressure": "Please pay the registration fee.",
            "credential_request": "Send your bank account number.",
            "unrealistic_claims": "This is a guaranteed selection.",
            "secrecy": "Keep this private.",
        }
        for name, text in samples.items():
            features = extract_linguistic_features(text)
            self.assertEqual(features[name]["value"], 1, name)
            self.assertTrue(features[name]["reason"], name)
            for other, feature in features.items():
                if other != name:
                    self.assertEqual(feature["value"], 0, f"{name} also fired {other}")

    def test_high_daily_pay_is_an_unrealistic_claim(self):
        features = extract_linguistic_features("Work from home and earn $500 per day.")
        reason = features["unrealistic_claims"]["reason"]
        self.assertEqual(features["unrealistic_claims"]["value"], 1)
        self.assertEqual(reason.count("500"), 1)
        self.assertEqual(features["financial_pressure"]["value"], 0)

    def test_ordinary_monthly_stipend_is_not_unrealistic(self):
        features = extract_linguistic_features("The stipend is ₹25,000 per month.")
        self.assertEqual(features["unrealistic_claims"]["value"], 0)

    def test_small_daily_number_is_not_high_pay(self):
        features = extract_linguistic_features("The team meets 5 per day in the office.")
        self.assertEqual(features["unrealistic_claims"]["value"], 0)

    def test_negated_fee_and_deposit_do_not_fire(self):
        features = extract_linguistic_features(
            "There is no registration fee and no deposit."
        )
        self.assertEqual(features["financial_pressure"]["value"], 0)
        self.assertEqual(features["financial_pressure"]["reason"], "")

    def test_coffee_and_feedback_are_not_fees(self):
        features = extract_linguistic_features(
            "You will get coffee, and we welcome feedback on the first day."
        )
        self.assertEqual(features["financial_pressure"]["value"], 0)

    def test_longer_phrase_is_quoted_once(self):
        features = extract_linguistic_features("Pay the registration fee.")
        reason = features["financial_pressure"]["reason"]
        self.assertIn('"registration fee"', reason)
        self.assertNotIn('"fee"', reason)

    def test_does_not_call_a_language_model(self):
        source = inspect.getsource(linguistic)
        self.assertNotIn("openai", source.lower())
        self.assertNotIn("openrouter", source.lower())
        self.assertNotIn("get_client", source)
        self.assertNotIn("backend.llm", source)


if __name__ == "__main__":
    unittest.main()
