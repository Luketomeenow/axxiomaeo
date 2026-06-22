# Authority & distribution checklist (Phase 4)

Off-platform work that strongly affects GEO/AEO citation probability.

## Per brand (repeat × 8)

### Google Business Profile
- [ ] NAP matches Brand Settings (name, phone, address)
- [ ] Primary category: Elevator service (or closest match)
- [ ] Service areas match `markets` in dashboard
- [ ] Weekly GBP post linking to a published AEO article URL

### NAP consistency
- [ ] Website URL = `wp_url` in Brand Settings
- [ ] Phone = `phone` in Brand Settings (same format everywhere)
- [ ] BBB / industry directories use identical NAP

### Reviews (real only)
- [ ] Do **not** use fabricated `aggregateRating` in JSON-LD
- [ ] Encourage Google reviews; respond to all reviews
- [ ] Optional: embed review widget on site (separate from schema)

### Cross-linking
- [ ] Axxiom corporate site links to each brand site
- [ ] Each brand footer/about mentions parent: Axxiom Elevator
- [ ] Published FAQ hubs link to core service pages (Repairs, Maintenance, Inspection)

### Multi-surface content
- [ ] Republish top FAQ answers on LinkedIn / YouTube (same facts, link back to live post)
- [ ] Press releases or case studies on axxiomelevator.com cite brand URLs

## Service page URLs in dashboard

In **Brand Settings → Service page URLs**, map each service to the live WordPress page (e.g. Repairs → `/repairs/`). The platform uses these when building Service JSON-LD `url` fields.
