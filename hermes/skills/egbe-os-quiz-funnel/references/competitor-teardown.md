# Competitor Teardown

Inspect reference funnels to answer a specific open experience question. Reuse
existing observations when they answer it; sustained advertising helps find
examples, not establish their conversion performance. Write the findings to
`egbe-docs/product/quizzes/<quiz-slug>/research.md`.

This is an optional evidence-gathering capability, independent of compilation.
Choose its scope from the question being investigated, not a mandatory sample
count or freshness window.

## Capabilities and budget

Read the live contracts before calling them: `GET $OS_URL/tools/skill`,
`GET $OS_URL/scrape/skill`, and `GET $OS_URL/search/skill`. Use only `OS_URL`
and `OS_API_KEY`; never a provider's own credentials.

Unless the caller sets another budget, stay within 8 paid provider calls (ad
library searches and actor runs) and 10 web searches, and walk at most 5
funnels. A lookup on the public page of an ad library is read in the browser
and is not a provider call. Save the handle of every asynchronous run before
polling and resume that run after a failure; do not start a replacement.

## 1. Collect candidates

Use the relevant discovery routes:

- **Seeds.** Funnel addresses supplied by the caller, and competitors named in
  the product documents or in completed market research.
- **Ad libraries.** Search with category keywords, competitor names, and words
  that signal a quiz: quiz, test, assessment, checkup, "find your".
  - The Meta Ad Library through OS:
    `POST $OS_URL/tools/meta-ad-library/search`. This route reads the library
    through Meta's API. By Meta's reference of that API, it returns an ad
    that reached no location in the European Union only when the ad is about
    social issues, elections, or politics. The route does not see commercial
    advertisers that deliver elsewhere:
    on 2026-09-28 five of six searches returned nothing, while the public
    page listed active ads in the United States for the same category.
  - The Meta Ad Library on its public page, which lists the active ads of
    every country, commercial ones included. Open
    `https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&q=<keyword or advertiser>`
    in the browser automation, without signing in: the page needs no
    account, and the teardown uses nobody's credentials. `country` takes a
    two-letter code or `ALL`. The page shows the number of active ads and,
    for each ad, the advertiser, the day the ad started running, and the
    address shown in the ad.
  - Google: an ad transparency actor discovered through the `scrape`
    capability.

  An empty result is the result of one route, not evidence that an advertiser
  does not advertise. Record it as empty, and repeat a search through OS on
  the public page.
- **Web search.** `POST $OS_URL/search/web/brave` for quiz pages in the category.

Include other countries, languages or adjacent categories when they help answer
the investigation question. Keep differences in audience, market and goal explicit;
do not treat observations from another setting as evidence for this one.

## 2. Qualify

Check that the destination is a flow of questions rather than a plain page.
Record the observed ad count and age when available. Libraries do not expose
commercial spend or conversion performance: never state or estimate a budget
from these signals or treat them as proof the UX works.

Select examples that address the investigation question, including relevant
differences in goal or market. There is no minimum number required for a valid
observation.

## 3. Walk

Use the shared local contract [walk-mechanics.v2.json](walk-mechanics.v2.json),
`funnel-walk.v2`. The installed skill is self-contained; no separate research
runtime or Lifecycle Capture installation is required.
The paid-call and per-attempt budgets bound resource use, not the completeness
of an observed funnel.

Open each funnel in a real browser at 390 by 844. Answer as the target buyer;
record the persona, answers, visible branch points, target market and observed
language, currency and consent banner/choice. Flag a market mismatch; currency
alone does not establish a country. Do not treat source/configuration text as an
observed screen.

Record every logical screen with its observed headline/text, kind, word counts,
options, answers, advance, CTA, offer, proof, price and notes. Save a real screenshot
per screen. A long page needs its significant blocks in a full-page capture or
additional screenshots; scrolling does not add logical screens. Distinguish teaser,
final personalized result and commercial offer, and price from salary or discount.
A dismissible popup is an auxiliary branch and does not replace the creative's
main route. Unknown/unseen is different from absent.

Before any submission, inspect the known forms without submitting and list each
form/URL, purpose and all exact values. Obtain the founder's explicit confirmation
in the conversation and retain its reference/version. Submit only those exact
approved forms and data; a new form, mandatory field or value requires a supplement
and another confirmation. A locally authored approval JSON is not human approval.
Complete approved lead forms, quizzes and webinar registrations to see the result,
price and conversion path after contact. Without approval preserve `needs_approval`
and continue independent observations.

Use a research mailbox supplied or confirmed by the caller and the agreed persona
name. Reserve one numeric plus alias (`<local>+NN@<host>`) per funnel in a local
private identity registry; reuse it on resume. When the caller supplies a shared
research registry, use it; otherwise keep a private registry alongside the quiz
research. Exact contact values stay in runtime records, not public research.md or
screenshots; capture forms before filling and scrub personalized screenshots.
The bundled `scripts/prepare-research-identity.py` reserves the alias with a lock
and atomic write; it imports no other skill. For standalone use:

```bash
python3 <skill-root>/scripts/prepare-research-identity.py \
  --registry <private-runtime>/identity-registry.json \
  --mailbox <confirmed-research-mailbox> --domain <competitor-domain> \
  --funnel-id <stable-funnel-id>
```

Read confirmation/result mail the same day if an authorized mailbox capability is
available. Confirm only an approved continuation, record the observed outcome and
mail receipt time, and leave missing mail `needs_email` with a reason. Lack of
mailbox access is an explicit block, not permission to use another identity.

An approved phone may use the US fiction range 555-0100 to 555-0199 in the required
full format only if the form accepts it. Otherwise stop with `phone`; never use a
random real number. Never create competitor accounts: record `needs_account`, and
continue only if the founder provides access. Never enter a card or pay. Record a
live sales-call booking screen (tool, slots, questions and conditions) and stop
before booking. CAPTCHA/bot verification and required SMS verification end the
walk with their recorded screen and reason; never bypass them.

Walk one main buyer path and additional relevant persona paths when they change
the offer, final result, price or conversion method. Keep paths distinct; they are
not extra competitors/funnels for recurring counts. Do not infer unseen branch
outcomes. Save progress after at most 40 screens per attempt, mark `budget` and
resume; 40 is not the total funnel length or its terminal outcome. Before submit
record intent, afterwards its observed response. After a crash check the outcome
without another submission; unknown outcome stays unknown. One real screen or an
immediate gate is valid evidence; never add fictional rows to meet a minimum.

## Findings and continuation

Keep source URLs, observation dates, market/persona, actual screens and screenshots,
approval reference (when applicable), stop reason and unknowns together in
`research.md`. Use the fields and statuses of the observation contract; headings
and a prescribed report shape are not compiler inputs. Keep additional paths
distinct from independent funnels. An observation made before an access or
permission boundary remains useful; do not fabricate the rest or repeat a
submission to fill a report.

Explain what the evidence supports for the investigation question and what it
does not. Recurrence describes independent examples, not measured performance;
take patterns, never copied claims, branding or invented numbers. Any accepted
experience change belongs in the project's existing plan/UX decisions, not in
a mandatory research adaptation or deviation ledger.

When a provider or browser is unavailable, preserve progress and the exact
failure. Empty API results do not prove absence: use another permitted relevant
source, within the call budget. A blocked teardown does not block independent
implementation of an already accepted experience.
