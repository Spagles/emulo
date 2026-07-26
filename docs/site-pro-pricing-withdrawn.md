# Withdrawn: the Emulo Pro pricing pane

Withdrawn from the live site on 2026-07-26 in `release: 0.6.1`. **Nothing here was
discarded.** Pro pricing is finished work that is waiting on a purchasable product,
not a rejected design.

It is parked in `docs/` rather than commented out inside `site/index.html` because
`vercel.json` serves the whole `site/` directory, so an HTML comment would still ship
`$9` and `$79` in the page source where crawlers, scrapers and LLM readers pick them
up. Withdrawn has to mean absent from the served bytes, not merely invisible.

The `.pro-plan` and `.pro-plans` CSS in `site/index.html` was left in place on purpose,
so restoring is a paste with no styling work.

## To restore

1. Replace the `<article class="price-pane price-pro">` block in `site/index.html`
   with the markup below.
2. Put the two Offer entries back into the `SoftwareApplication` structured data,
   after the `Open-source Emulo` offer.
3. Restore the section heading copy: label `Open source + managed continuity`,
   heading `Start free. Add continuity when your workflows depend on it.`
4. Update `tests/test_site_pricing.py`, which currently **fails** if any plan price,
   discount, `Coming soon` button, checkout host, or paid-account URL reappears.
   That guard is intentional. Flip it back deliberately, in the same commit that
   makes checkout real, so the page and the product can never disagree again.
5. Confirm the prices are the live Polar prices before publishing. Do not trust the
   numbers below to still be current.

## The pane, exactly as it was

```html
      <article class="price-pane price-pro">
        <span class="label pro-label">Emulo Pro</span>
        <h3>Managed continuity for the way you work.</h3>
        <p>Choose the managed layer when your approved Emulo generations need to follow you safely. Paid capabilities open only after they are verified.</p>
        <ul class="price-list">
          <li>End-to-end encrypted continuity across up to five devices</li>
          <li>Managed pairing, revocation, and device status</li>
          <li>Up to 500 encrypted generations within 64 MiB</li>
          <li>Conflict-safe encrypted history with local rollback intact</li>
          <li>30-day encrypted export and recovery window after access ends</li>
          <li>Raw session logs and decryption keys stay local</li>
        </ul>
        <div class="pro-plans">
          <div class="pro-plan">
            <div><strong>Monthly</strong><small>Flexible access</small></div>
            <div class="amount">$9 <span>/ month</span></div>
            <a href="https://emulo-production.ohad1306.workers.dev/account" aria-label="Choose Emulo Pro monthly">Choose monthly</a>
          </div>
          <div class="pro-plan">
            <div><strong>Annual</strong><small>One year</small></div>
            <div class="amount"><s>$108</s> $79 <span>/ year</span><em>Save 27%</em></div>
            <a href="https://emulo-production.ohad1306.workers.dev/account" aria-label="Choose Emulo Pro annual">Choose annual</a>
          </div>
        </div>
      </article>
```

## The structured data offers, exactly as they were

```json
    { "@type": "Offer", "name": "Emulo Pro Monthly", "price": "9", "priceCurrency": "USD" },
    { "@type": "Offer", "name": "Emulo Pro Annual", "price": "79", "priceCurrency": "USD" }
```
