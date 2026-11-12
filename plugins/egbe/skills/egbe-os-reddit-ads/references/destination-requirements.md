# Reddit destination requirements

Use for Reddit destination paths only. Reuse the common journey inspection;
do not invoke the full Reddit launch/readiness workflow for this review.
Sources were checked 2026-09-29; read the applicable current sections.

For a complete visitor-path review, apply the `egbe-os-destination-readiness` skill with
this reference in one audit run. If missing locally, its full bundle is available
at `GET $OS_URL/skills/destination-readiness`.

## Apply to the actual click destination

[Editorial requirements — URL and Landing Page Policies](https://business.reddithelp.com/s/article/Reddit-Advertising-Policy-Editorial-Requirements#url-and-landing-page-policies)
require matching display/landing URLs, availability of the advertised offering,
usable links/navigation, and language consistent with the ad. Inspect links on
the landing page to materially relevant prohibited/restricted offerings as well,
not just the main offer. Cite the specific category rule if one applies.

For existing ads, use read-only OS evidence of the actual click URL as well as
the post's destination: [Reddit documents](https://ads-api.reddit.com/docs/v3/guides/programs/campaign/match-destination-and-click-url)
that changing creative does not automatically update the click URL. Trace the
observed route before calling different URLs a mismatch; a legitimate tracker
can lead to the intended page. This is destination resolution, not a campaign
structure audit, and does not authorize editing either resource.

## Apply to collection

[User Data Collection](https://business.reddithelp.com/s/article/user-data-collection-policy)
requires secure, responsible handling for disclosed purposes. Reuse the common
form/document evidence to identify an actual disclosure or security gap. Do not
claim this source mandates literal `/privacy` or `/terms` paths.

Help Center articles may require a rendered browser. If the policy body cannot
be read, record that limit rather than treating the site's loading shell as
the policy or a community anecdote as a universal requirement. Return affected
paths, evidence, source section and repair/recheck; moderation is a separate fact.
