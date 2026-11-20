# Specification Contract

One folder holds everything about one quiz:

| Path | Author | Meaning |
|---|---|---|
| `egbe-docs/product/quizzes/<quiz-slug>/quiz.json` | Agent | The executable specification of the accepted experience. |
| `egbe-docs/product/quizzes/<quiz-slug>/QUIZ.md` | Compiler | The readable specification for review. |
| `egbe-docs/product/quizzes/<quiz-slug>/quiz.public.json` | Compiler | The part of the specification the page renders. |
| `egbe-docs/product/quizzes/<quiz-slug>/validation.json` | Compiler | The receipt of the last compile: status, date, hashes, counts, consent and reachability diagnostics. |

Resolve `egbe-docs/` from the product repository root. Keep it with the product source and use the repository's versioning workflow
when a commit is in scope. Optional research can live beside it; no report is
required to compile.

## Compile

```bash
python3 <skill-root>/scripts/compile-quiz-spec.py \
  --workspace <workspace-root> --quiz-slug <quiz-slug>
```

The compiler reads `quiz.json`. Contract errors block compilation; nonblocking
diagnostics remain in `validation.json.warnings`. No research age, prescribed
length, wording limit or deviation justification is required.

- When the specification is ready, it writes the three compiled files, with
  `"status": "ready"` in the receipt.
- When it is not, it removes `QUIZ.md` and `quiz.public.json` of an earlier
  version and writes the receipt with `"status": "not_ready"` and the
  problems, so that nothing stale can be mistaken for current.
- `--check` validates without writing or removing anything.
- `--today` fixes the date for reproducible tests. Do not use it to compile a
  quiz.

The compiler checks structure and consistency. It does not know whether a
statement is true.

## General rules

- Unknown fields are errors.
- An id starts with a lowercase letter and contains lowercase letters, digits,
  `-`, and `_`, 40 characters at most. The
  ids of screens and results are unique among both; option ids are unique on
  their screen.
- The name of a query parameter starts with a lowercase letter and contains
  lowercase letters, digits, and `_`. It cannot be `email`, `mail`, `name`,
  `phone`, or `tel`.
- A text the visitor reads is one line of plain text without line breaks. It
  contains no claim to avoid.
- A same-origin path starts with `/` and has no fragment. An address is an
  absolute `https` address without credentials or a fragment. Neither carries
  personal data in its query.

## Specification

A complete example is in
`assets/examples/egbe-docs/product/quizzes/books-checkup/quiz.json`. It was compiled with
`--today 2026-09-28`.

```json
{
  "contract": "quiz-funnel-spec-v1",
  "quiz_slug": "books-checkup",
  "product_slug": "example-books",
  "route": "/quiz/books-checkup",
  "language": "en",
  "title": "Books checkup",
  "ui": {"back": "Back", "progress": "Step {current} of {total}"},
  "inputs": {},
  "goal": {},
  "proof": [],
  "screens": [],
  "results": []
}
```

- `quiz_slug` and `product_slug`: lowercase letters, digits, and `-`.
  `quiz_slug` equals the name of the folder.
- `route`: a lowercase path without a query or a trailing slash. Its first
  segment cannot be `account`, `admin`, `api`, `auth`, `checkout`,
  `dashboard`, `login`, `logout`, `pricing`, `privacy`, `register`, `signup`,
  or `terms`, and it cannot be the homepage.
- `language`: a language tag such as `en`, `es`, or `pt-BR`. Add the region
  only when the copy is written for that region.
- `title`: the title of the page in the browser, in the language of the quiz.
- `ui.back`: the label of the back control. `ui.progress`: the label of the
  progress indicator with the placeholders `{current}` and `{total}`. `{total}`
  counts every screen before the result, questions and interstitial screens
  alike, so word the label as steps, not as questions.

### `inputs`

```json
{
  "product": "What the product is and does.",
  "application": {"repository": "example-books", "url": "https://example-books.egbe.app"},
  "segment": {"name": "", "situation": "", "problem": ""},
  "offer": {
    "promise": "",
    "mechanism": "",
    "terms": "",
    "claims_to_avoid": [],
    "not_for": []
  },
  "traffic": {"channels": ["meta_ads"], "geographies": ["US"], "promise": ""},
  "sources": [{"label": "Caller request", "ref": "request"}]
}
```

- `offer.claims_to_avoid` and `offer.not_for` may be empty lists.
- `traffic.channels` names the channels, for example `meta_ads`, `google_ads`,
  `reddit_ads`, `linkedin_ads`, `openai_ads`, `outreach_email`.
- `traffic.geographies` holds two-letter country codes. The compiler lists
  those that need consent in the receipt.
- `traffic.promise` is the text of the ad or message. Leave the field out when
  no ad exists yet.
- `sources[].ref` is `request`, `answer`, or the path or address of a
  document.
- Proof that exists is recorded under `proof`, not here. A product without
  proof has an empty `proof` list.

### `goal`

```json
{
  "type": "call",
  "statement": "The quiz should get visitors to book the free books review call.",
  "destination": {"kind": "booking_url", "url": "https://cal.example.com/books-review"}
}
```

`statement` is optional context from the accepted project decisions. The
destination depends on the goal:

| Goal | `kind` | Fields |
|---|---|---|
| `call` | `booking_url` | `url`; optional `result_param`, `fallback_params` |
| `call` | `lead_form` | `action` (same-origin path), `fields`, `field_labels`, `submit_label`, `error`, `success` (`headline`, `body`); optional `consent_note` |
| `signup` | `signup` | `path` (same-origin) |
| `payment` | `checkout` | `path` (same-origin), `plan_key`, `price`; optional `plan_param` (default `plan`) |

- `fields` may contain `name`, `email`, `phone`, and `company`, each once, and
  must contain `email` or `phone`. `field_labels` has one label per field.
- `result_param` must not already be in the query of `url`.
- The checkout `path` must not already carry the plan parameter.
- `price` is the price with its period, exactly as the product's plan catalog
  states it, for example `$95 per month`. Every result that leads to the
  checkout must contain it, character for character, in a text that every
  visitor of that result reads: its headline, its body, the label or the note
  of its call to action, or a point that is never left out. A point that
  quotes a question with an escape option is left out for visitors who chose
  that option, so the price in such a point does not count.
- See [conversion-handoff.md](conversion-handoff.md) for what each field does.
- A request form that continues to a scheduling page keeps the kind
  `lead_form`. The scheduling address is not a field of the specification;
  [conversion-handoff.md](conversion-handoff.md) says where it is kept and
  recorded.

### `proof`

```json
{"id": "review-summary", "kind": "fact", "text": "Shown text.", "source": "Where it can be checked"}
```

`kind` is `count`, `fact`, `logo`, `statistic`, or `testimonial`. A
`testimonial` needs `author`; a `statistic` needs `citation`. Every entry must
be shown on a screen or a result; remove what is not shown.

### `screens`

The visitor passes the screens in order, then sees a result. The first screen
may be a question or an interstitial, including an introduction.

```json
{
  "id": "worries",
  "type": "question",
  "select": "multi",
  "headline": "What worries you most?",
  "hint": "Choose all that apply.",
  "purpose": "build_case",
  "button": "Continue",
  "options": [
    {"id": "deadline", "label": "Tax deadline", "phrase": "the tax deadline"},
    {"id": "nothing", "label": "None of these", "escape": true}
  ]
}
```

- `select` is `single` or `multi`. A `multi` question needs `button` and
  cannot be passed with nothing chosen. A `single` question must not have a
  button. `hint` is optional for either kind.
- Optional private `purpose` is `personalize`, `qualify`, or `build_case`; it
  explains an answer's use and does not reach the browser. An unused answer is
  a diagnostic, not a compilation failure.
- `lead` is optional introductory text on a question.
- `options`: a non-empty list. `label` is the text of the button. `phrase` is the same
  answer worded for the middle of a sentence; tokens use it when it exists.
- `"escape": true` marks the option for visitors to whom no other option
  applies or who prefer not to answer. A question has at most one and at least
  one option besides it. On a multi-select question it excludes the others.
- `"sensitive": true` requires an escape option and keeps the chosen option in
  the visitor's browser.

```json
{
  "id": "halfway",
  "type": "interstitial",
  "kind": "encouragement",
  "headline": "You are halfway there",
  "body": "Three more answers and you will see what your books need first.",
  "button": "Continue",
  "variants": [
    {
      "when": {"all": [{"screen": "behind", "any_of": ["many", "year"]}]},
      "headline": "This is what a catch-up is for",
      "body": "Books that are {{answer:behind}} can be reconciled month by month."
    }
  ]
}
```

- `kind` is `encouragement`, `proof`, or `teach`. A `proof` screen needs
  `proof_ids`.
- `body`, `points`, `media`, and `proof_ids` are optional.
- `variants` is optional. The first variant whose `when` matches replaces the
  fields it contains; the screen's own fields apply to everyone else. A
  variant changes `headline`, `body`, `points`, `media`, or `proof_ids`, never
  the button. Its conditions may name only questions that come before the
  screen. A variant that no answer can reach, or variants that leave the
  screen's own texts unreachable, are errors.

### `results`

Results are tested in order and the first match is shown. The last result has
no `when` and is the default. A `not_fit` result is shown as soon as the
answers given decide it, that is, when every answer the remaining questions
could receive leads to it; the remaining screens are skipped. A `not_fit`
result whose headline or body quotes a question that is not answered yet
waits for that question.

```json
{
  "id": "catch-up",
  "fit": "fit",
  "when": {"all": [{"screen": "behind", "any_of": ["many", "year"]}]},
  "headline": "Your books need a catch-up first",
  "body": "On the free 20-minute review we list the missing months.",
  "points": ["Your books: {{answer:behind}}", "On your mind: {{answer:worries}}"],
  "cta": {"label": "Book the free review", "note": "The call takes 20 minutes."}
}
```

- `fit` is `fit`, `partial`, or `not_fit`. A `not_fit` result requires an
  entry in `inputs.offer.not_for`.
- `cta` has a `label` and an optional `note`. Without a `destination` it leads
  to the destination of the goal. At least one `fit` or `partial` result must
  do so.
- A `cta` may carry its own `destination`: `{"kind": "link", "path": "/..."}`
  or `{"kind": "link", "url": "https://..."}`. It must not lead to the
  destination of the goal. A `not_fit` result needs its own destination or
  `"cta": null`; only a `not_fit` result may have `"cta": null`.
- `points`, `media`, and `proof_ids` are optional.
- A result that no answer can reach is an error: its conditions cannot be met,
  or earlier results catch every answer that meets them.
- A shared result is supported when the accepted experience records answers
  for a later use rather than personalizing the result in this runtime.

### `media`

```json
{"src": "/quiz/books-checkup/summary.png", "alt": "A written summary of a review", "source": "Summary sent to a client on 2026-08-12, names removed"}
```

`src` is a same-origin path or an address. `alt` describes the image to a
visitor who cannot see it. `source` is for the founder and does not reach the
page.

### Conditions

`when` holds exactly one of `all` or `any`, each a list of conditions. A
condition names a question `screen` and exactly one of `any_of` or `none_of`,
each a list of option ids of that question. For a multi-select question,
`any_of` matches when at least one listed option was chosen and `none_of` when
none was.

The condition of a result must not name a sensitive question.

### Tokens

`{{answer:<question id>}}` is replaced by what the visitor chose.

Sensitive answers cannot be used in tokens: interstitial and result copy is
not masked by the question's recording selector. Keep those answers private;
this runtime has no private result-text rendering mode.

| Where | Which questions | What appears |
|---|---|---|
| `headline` and `body` of an interstitial screen, a variant, or a result | Single-choice questions without an escape option | The `phrase` of the chosen option, or its `label` |
| `points` of an interstitial screen, a variant, or a result | Any question | The chosen options separated by commas. The whole point is left out when the visitor chose the escape option, so a point that quotes such a question must not carry what every visitor has to read. |
| Anywhere else | — | An error |

An interstitial screen may quote only questions that come before it. Write
every sentence so that each possible answer reads well in it, and give options
a `phrase` when their label does not.

### Diagnostics and bounds

`multi_select_escape` flags a multi-select with no declining option;
`unused_answer` flags a declared personalization/qualification answer with no
local rule or token. Both are nonblocking: exhaustive choices or an external
follow-up can make them intentional. A sensitive question still needs a refusal
option and cannot choose a public result.

Exhaustive reachability is bounded to 200,000 combinations, including the work
needed to construct multi-select answer classes. If skipped, the receipt says
`reachability: "not_checked"` and identifies affected rules in `warnings`; this
is not a passing check. Verify relevant paths separately before release. The
last default result remains required. Runtime early-result inference is separately
bounded; when it cannot prove an early result it continues the accepted screens
and resolves the result from the completed answers.

The compiler checks configured `claims_to_avoid` (case/accent insensitive) and
exact configured checkout prices. It does not use matching digits as proof of
truth. Check claims and source attribution against real evidence separately.

## Hashes

The receipt and `quiz.public.json` carry hashes:

- `spec_sha256` names the specification and changes with any edit of
  `quiz.json`.
- `public_sha256` changes only when the page itself changes; a visitor's saved
  progress starts over when it does.
