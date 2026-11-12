# LinkedIn destination requirements

Use for the LinkedIn paths in a destination review, independently of account,
campaign and conversion readiness. Reuse the common journey evidence.

For a complete visitor-path review, apply the `egbe-os-destination-readiness` skill with
this reference in one audit run. If missing locally, its full bundle is available
at `GET $OS_URL/skills/destination-readiness`.

Source: [LinkedIn Advertising Policies](https://www.linkedin.com/legal/ads-policy),
sections 4 and 6; checked 2026-09-29. Read current wording for a policy finding.

- **Offer and identity:** the product must match the ad; advertised prices,
  discounts and offers must be easy to find from its link. Identify unsupported
  affiliation or confusing brand transitions without treating an explained
  parent/provider identity as an error.
- **Link behavior:** the display and destination domains must match, and members
  must reach the same destination/landing page from the ad. Inspect unexpected
  redirects, landing-triggered pop-ups and whether Back/navigation works. A
  deliberate later booking/checkout link is a separate journey step.
- **Collection security:** LinkedIn requires HTTPS for sensitive information,
  including login, financial and specified personal information. Inspect the
  applicable collection step, not merely the initial page's certificate.
- **Privacy:** where cross-site tracking is actually observed, assess disclosure
  and consent against section 6. Do not infer it from the absence of a cookie
  banner or audit whether conversion instrumentation is installed correctly.

For each issue return the affected path, exact observation, policy section and
smallest repair with a recheck condition. An inaccessible region or browser
variant remains unverified; successful inspection is not LinkedIn approval.
