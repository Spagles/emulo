"""Guards the README's commercial boundary.

Rewritten 2026-08-18. This file once asserted the presence of an
"Open source and Emulo Pro" section that sold a hosted continuity layer nobody
could buy: both Polar products were Private and the site's pricing pane was
withdrawn, so the link it gave led to a page with no prices on it.

The rule that survives all of that is not "no prices in the README". It is that
**every price the README names must have a real way to pay it.** Two do now:

  $300 Profile Build   by invoice or PayPal, stated as outside the store
  $12 / $99 Emulo Pro  through Polar, via the account page

So the guard checks that the retired prices never come back, that every price
named is one somebody can actually pay, that the local boundary keeps being
stated, and that no secret reaches the file. It no longer forbids naming a
price, because naming a purchasable one is now correct.
"""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"

SECTION = "## Open source and privacy"

# Prices published while nothing could be bought at them. They never return.
RETIRED_PATTERNS = [
    r"\$9\b",
    r"\$79\b",
    r"\$108\b",
    r"Save 27%",
]

# A secret or a raw checkout host has no business in a public README.
LEAK_PATTERNS = [
    r"buy\.polar\.sh",
    r"checkout\.polar\.sh",
    r"polar_(?:oat|sk)",
    r"github_client_secret",
    r"polar_webhook_secret",
]

# Every price the README may name, and the rail that can actually take it.
PAYABLE = {"300": "invoice or PayPal", "12": "Polar", "99": "Polar"}


class ReadmeCloudBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = README.read_text(encoding="utf-8")

    def test_readme_states_the_local_boundary(self):
        self.assertIn(SECTION, self.readme)
        section = self.readme.split(SECTION, 1)[1].split("\n## ", 1)[0]
        self.assertIn("MIT", section)
        self.assertIn("without an account", section)
        # The one honest exception has to stay stated, not quietly dropped.
        self.assertIn("hosted model", section)
        self.assertIn("local model", section)

    def test_retired_prices_never_return(self):
        for pattern in RETIRED_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIsNone(
                    re.search(pattern, self.readme),
                    f"README names {pattern!r}, which was withdrawn because "
                    "nothing could be bought at that price.",
                )

    def test_every_price_named_has_a_way_to_pay_it(self):
        for amount in sorted(set(re.findall(r"\$(\d+)", self.readme))):
            with self.subTest(amount=amount):
                self.assertIn(
                    amount, PAYABLE,
                    f"README names ${amount} but nothing sells at that price. "
                    "Add the rail to PAYABLE, or take the number out.",
                )

    def test_no_secret_or_raw_checkout_host_leaks(self):
        for pattern in LEAK_PATTERNS:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, self.readme, re.I))


if __name__ == "__main__":
    unittest.main()
