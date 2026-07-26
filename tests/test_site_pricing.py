import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site" / "index.html"
ACCOUNT_URL = "https://emulo-production.ohad1306.workers.dev/account"


class SitePricingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = SITE.read_text(encoding="utf-8")

    def pricing(self):
        return self.html.split('id="pricing"', 1)[1].split("</section>", 1)[0]

    def test_pricing_is_reachable_and_names_both_product_paths(self):
        self.assertIn('href="#pricing"', self.html)
        self.assertIn('id="pricing"', self.html)
        self.assertIn("Free and open source", self.html)
        self.assertIn("Profile Build", self.pricing())

    def test_no_price_is_shown_for_anything_that_cannot_be_bought(self):
        # Pro is not purchasable yet. The page must not display a plan price,
        # a struck-through comparison, or a discount for it anywhere.
        pricing = self.pricing()
        self.assertIn("$0", pricing)
        self.assertIn("Get Emulo", pricing)
        for rejected in ("$9", "$79", "$108", "Save 27%", "Choose monthly",
                         "Choose annual", "Coming soon", "/ month", "/ year"):
            self.assertNotIn(rejected, pricing)

    def test_structured_data_declares_no_price_the_site_does_not_sell(self):
        # A visible price and a schema.org Offer must never disagree: search
        # results were advertising $9 and $79 while checkout was closed.
        head = self.html.split("</head>", 1)[0]
        self.assertIn('"price": "0"', head)
        for rejected in ('"price": "9"', '"price": "79"',
                         "Emulo Pro Monthly", "Emulo Pro Annual"):
            self.assertNotIn(rejected, head)

    def test_pricing_keeps_free_capable_and_does_not_claim_sync_is_live(self):
        pricing = self.pricing()
        for text in ("Free and open source", "MIT", "local", "No subscription"):
            self.assertIn(text.lower(), pricing.lower())
        self.assertNotIn("available today", pricing.lower())
        self.assertNotIn("unlimited", pricing.lower())

    def test_paid_path_is_contact_only_and_privacy_bounded(self):
        pricing = self.pricing()
        self.assertIn("mailto:", pricing)
        self.assertIn("Your session logs never leave your machine", pricing)
        self.assertIn("Three business days", pricing)
        self.assertIn(".price-pro .price-list li", self.html)

    def test_open_source_local_product_is_not_weakened(self):
        pricing = self.pricing()
        self.assertIn("MIT", pricing)
        self.assertIn("local", pricing.lower())
        self.assertIn("you.md", pricing)
        self.assertIn("No subscription", pricing)

    def test_static_site_exposes_no_checkout_surface_or_secret(self):
        # No half-removed paid path: the account boundary and every checkout
        # host stay off the static page while Pro is withdrawn.
        self.assertNotIn(ACCOUNT_URL, self.html)
        for host in ("checkout.polar.sh", "sandbox.polar.sh", "buy.polar.sh"):
            self.assertNotIn(host, self.html)
        self.assertNotRegex(
            self.html,
            re.compile(r"(?:polar_(?:oat|sk)|github_client_secret|polar_webhook_secret)", re.I),
        )

    def test_static_site_does_not_embed_production_product_ids(self):
        self.assertNotIn("ce99808b-4e11-4cec-bc31-d9654d558e08", self.html)
        self.assertNotIn("b6535378-b1bd-40ee-bd37-96a03abec2f2", self.html)


if __name__ == "__main__":
    unittest.main()
