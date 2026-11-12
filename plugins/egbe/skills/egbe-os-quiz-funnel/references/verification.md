# Verification

Verify the changed behavior locally. When a release is in scope, repeat the
relevant checks on the deployed route; do not claim live verification from a build. Create no real booking,
account, request, or payment, and write no synthetic events into production
statistics.

## Before deploy

- `compile-quiz-spec.py --check` reports the specification as ready and prints
  its hash.
- The `spec_sha256` of the `quiz.public.json` inside the application equals
  that hash.
- The application's lint and build pass.
- Review `validation.json.warnings`. `reachability: "not_checked"` needs
  separate path verification; it is not a passing exhaustive check.

## On the live route

Before the first page load of the verification session, set up the browser you
use so that nothing reaches production statistics: let the analytics tracker
load but block the requests it sends, and block the session recorder and every
advertising pixel. Keep this until the session ends. The blocked requests of
the tracker are the evidence for step 7.

Check on a phone-sized viewport of 375 by 667 and on a desktop viewport.

1. **Route.** Opening the address directly shows the accepted first screen, not the
   homepage, a sign-in page, or an empty page. The page title, the language of
   the quiz, and `noindex` are set.
2. **First screen.** The accepted first screen and its controls remain usable on
   the target mobile viewport, including when long content needs scrolling. Nothing scrolls sideways on any screen.
3. **Movement.** A single-choice option advances without a button. A second
   tap right after the first does not answer the next question. A multi-select
   question does not advance without a choice, and switching an option keeps
   focus and scroll position. An interstitial screen has one button. Refusal and navigation follow the accepted experience. The back control and the browser's own back return to the
   previous screen and keep the answers. Reloading keeps the progress. After a
   reload on the third screen, the back control pressed twice leads to the
   first screen, and the browser's back from there leaves the quiz.
4. **Screens.** Every variant of an interstitial screen appears for the
   answers that select it, and the screen's own texts appear for the others.
5. **Results.** Walk one path to every result. Each shows its own headline,
   body, points, and image; every token is replaced by the chosen answer; a
   point whose question was declined is absent; the default result appears
   when no rule matches. Every image loads and shows what its `source` says.
   A `not_fit` result appears right after the answer that decides it, without
   the remaining questions; the back control and the browser's back return to
   that question, and another answer to it continues with the next screen.
6. **Call to action and destination.** For each result the label, the note
   under the button, and the destination match the specification, and a
   `not_fit` result does not lead to the goal.
   - `booking_url`: the link opens the scheduling page. For a visit that
     arrived with campaign parameters the link carries them; for a visit
     without them it carries the fallback values. Stop there.
   - `lead_form`: labels, consent note, and the failure state appear as
     specified. The endpoint rejects an invalid request and stores nothing.
     Submit a valid request only when the product can mark and remove a test
     record.
   - `lead_form` that continues to a scheduling page: mock malformed contact,
     other rejection, server error, no response and confirmed save. Each follows
     the accepted recovery behavior; navigation alone never reports a saved
     request. The calendar URL carries campaign/result identifiers, never
     contact details. Returning with Back does not resubmit the form.
   - `signup`: the link reaches the signup route. With the private validation
     identity prepared by the product's authentication work, confirm that the
     first page after signup shows the restored result in the same tab, and
     the normal first page when no result is stored.
   - `checkout`: the link reaches the checkout route with the plan. The price
     and period on the result equal those of the plan catalog. Use the
     validation mode of the product's checkout; do not pay.
7. **Analytics.** The blocked requests of one complete path carry the event
   names and values that [measurement.md](measurement.md) lists, the first
   answer included, and each event once: an answer that appears twice points
   to a binding that repeats what the runtime had already kept. Where the
   path ends in a link, the click of that link carries its keys in
   kebab-case. The answer to a sensitive question is in none of them.
8. **Access.** Complete one path with the keyboard only. Focus is visible and
   moves to each new headline. Text contrast is sufficient. With a
   reduced-motion preference the quiz still works.
9. **Weight.** On a throttled mobile connection the first screen can be
   used as soon as it is visible. Where the first screen is part of the
   delivered document, hold back the request for the page's module, tap an
   option, and release the request: the option shows as chosen while the
   module is held back, the second screen appears after the release, and the
   event of the first answer is among the blocked requests, once. For an
   interstitial introduction, test an early continue tap and ensure it advances
   once, also when saved progress exists. The route
   loads no feature of the product's application.
10. **Links and consent.** The privacy, terms, and contact links work. The
    consent mechanism appears where [implementation.md](implementation.md)
    requires it.
11. **The rest of the product.** The homepage, signup, and checkout respond as
    they did before the change.

## When a check fails

Fix the cause, redeploy when release is in scope, and repeat the failed check and the ones that depend
on it. A failure in the copy or the rules is fixed in `quiz.json` and compiled
again. When the cause is outside the quiz, such as a scheduling page that does
not open, report it as an open launch condition with the evidence instead of
working around it.
