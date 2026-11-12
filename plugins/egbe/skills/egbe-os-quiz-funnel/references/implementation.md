# Implementation

Build the quiz as one new route of the product's existing application. Keep
the product's framework, package manager, lockfile, Dockerfile, monitoring,
analytics, and deploy configuration.

## 1. Inspect the application

Before writing code, find:

- the framework and how it declares routes;
- the design in use: `egbe-docs/product/design.md` when it exists, and the styles, fonts,
  and components of the current pages;
- the analytics wiring: the shared tracker and the session recorder in the
  application shell, and how the product's own pages hand their events over,
  through `window.umami.track` or through `window.__egbeAttribution.track`;
- the legal pages and the consent mechanism, if any;
- the routes of signup and checkout when the goal needs them.

## 2. Add the engine and the specification

- Copy `assets/engine/quiz-engine.mjs`, `quiz-history.mjs`, and their
  `.d.mts` files into the application source unchanged. The engine holds the
  state, resolves what each screen and the result say, builds the destination,
  and describes the analytics events. The history module keeps the entries of
  the browser's history consistent. Neither has dependencies or touches the
  page.
- Copy the compiled `quiz.public.json` into the application source and import
  it, so that it is delivered with the page. Do not fetch it after the page
  has loaded, do not retype copy into components, and do not edit the copy of
  the file; change `quiz.json` and compile again.
- Create the quiz with `createQuiz(spec, { storage, onEvent })`. `onEvent`
  receives the analytics descriptors that [measurement.md](measurement.md)
  explains. `storage` is the session storage of the browser: read
  `window.sessionStorage` inside a `try` block, and pass `null` when it is
  blocked and wherever the code runs on the server. The engine works without
  storage.
- Where the page is rendered before the browser runs its module, on the server
  or at build time, render the accepted first screen there and show saved progress
  once the module has started in the browser, so that both renderings agree.
  `assets/reference/quiz-first-screen.mjs` provides a dependency-free escaped
  renderer for that first screen. Load `quiz-bootstrap.js` as a small classic
  script after that markup and before the page module to capture early actions.
  The reference binding drains them through `quiz-early-actions.mjs` once,
  against the restored screen; port the same behavior to the product framework.

## 3. Bind the engine to the page

`assets/reference/quiz-page.mjs` is a complete binding for a plain page. It
shows which engine call belongs to which interaction. Port its behavior to the
product's framework; do not ship its styling.

| Interaction | Engine call |
|---|---|
| Render the current screen | `snapshot()` |
| Visitor chooses an option of a single-choice question | `select(optionId, screenId)` |
| Visitor switches an option of a multi-select question | `toggle(optionId, screenId)` |
| Visitor presses the button of a multi-select or interstitial screen | `advance(screenId)` |
| Render the result | `result()` and `cta(attribution)` |

`screenId` is the id of the screen the visitor acted on. The engine ignores an
action that arrives after the screen has changed. An interstitial screen in a
snapshot already carries the texts, points, image, and proof for the answers
given. Render the note of a call to action directly under its button.

`onEvent` hands each descriptor to analytics exactly once, in the way the
product's own pages do. The reference binding sends through
`window.umami.track` and keeps its own queue while the tracker loads. Where
the product hands events to `window.__egbeAttribution.track(name, data)`, do
not repeat an event when that call returns `false`: while the tracker is
loading, the runtime has kept the event, and a second hand-over counts the
answer twice. [measurement.md](measurement.md) describes both under Delivery.

Going back belongs to the engine and to the history together. Create the
history with `createQuizHistory(window.history, spec.quiz_slug)`:

| Moment | Calls |
|---|---|
| The page shows the quiz | `history.mount(index)` with the index the engine starts on |
| The visitor has moved forward to a screen | `history.forward(index)` |
| The visitor presses the back control | `history.back()`; when it returns `false`, `quiz.back()` and then `history.replace(index)` |
| The browser reports a move (`popstate`) | `history.follow(event.state)`; when it returns an index, `quiz.goTo(index)` |

## 4. Required behavior

- The accepted first screen is present when the page loads: a question or an
  interstitial introduction. Do not insert an unrequested loading step.
- `select` and `advance` return the result at once when the answers decide a
  `not_fit` result. Render it like any result: `history.forward(index)` adds
  one entry for the jump, and the back control returns to the deciding
  question through the history.
- Where the first screen is part of the delivered document, a visitor can
  tap an option before the page's module is ready. That tap must not be lost.
  Until the module starts, a few lines of script in the document keep the
  tap in a variable of the page, as the ids of its screen and its option, and
  show the option as chosen. For a single-choice question the last tap
  counts. For a multi-select question every tap is kept in order, and the
  button stays disabled until the module has started. When the module starts,
  it applies the kept tap through the same path as a tap it receives itself:
  the answer to a single-choice question is stored and reported, and the next
  screen appears. It applies the tap only when the quiz starts on the screen
  that was tapped: a visitor with saved progress starts further on. For an
  introductory interstitial, preserve its continue action once, using its
  screen ID; do not replay it against a restored later screen.
- A single-choice option shows its selected state for a moment, 150 to 250
  milliseconds, and the next screen appears. During that moment every other
  control is ignored. Under a reduced-motion preference the next screen
  appears at once.
- For about a third of a second after a new screen appears, taps are ignored:
  the second tap of a double tap must not answer the next question.
- Switching an option of a multi-select question changes that option in
  place. The screen is not rendered again, and focus and scroll position stay
  where they are.
- The button of a multi-select question is disabled until an option is chosen.
- A back control and a progress indicator are present from the second screen
  on. The engine has no skip operation; represent an accepted refusal as an
  escape option or choose another implementation when the UX requires skipping.
- The browser's own back returns to the previous screen instead of leaving the
  quiz, and from the first screen it leaves the quiz. The history module
  adds an entry for each screen the visitor moves forward to, without changing
  the address, and keeps what the application's router stores in an entry.
  Stop listening to the browser when the quiz is removed from the page.
- While the browser steps back, a second press of the back control is
  ignored.
- Reloading the page keeps the progress and the history: the back control and
  the browser's back step through the same screens as before the reload.
- Verify responsive layout and keyboard/touch access on the target viewport,
  including long accepted option lists. No content or controls may be clipped
  or made unreachable; vertical scrolling is supported.
- Options are real buttons at least 48 pixels high; the whole row responds to
  a tap.
- Focus moves to the headline of each new screen, and to the confirmation
  after a request form is sent. Focus is visible and contrast is sufficient.
- The element that contains the quiz declares the language of the quiz, also
  when the application declares another one for the page.
- Preserve the accepted navigation and the product's privacy, terms and contact
  links. Do not remove unrelated navigation as a default quiz convention.

## 5. Design

Use the product's design: its type, color, shape, and tone. A visitor who
later opens the homepage must recognize the same product.

An image that says something about the product or the offer is content: it is
the `media` of a screen or a result in the specification. Decoration, such as
an icon on an option, is design and stays in the code. For decoration use the
product's own material or the Egbe OS `images` capability.

## 6. Weight

Visitors arrive from ads on phones and mobile networks.

- Opening the address of the quiz directly shows the accepted first screen. It does
  not show the homepage, a sign-in page, or an empty page that fills in later.
- The route imports the engine, the specification, and the product's shared
  shell and styles. It imports no feature of the product's application, such
  as its dashboard or editor.
- Where the framework renders on the server, the first screen is part of the
  delivered page. A page built for static hosting can deliver it as well; see
  the framework notes.
- Images are sized and compressed; images of later screens load when they are
  needed.

## 7. Indexing, privacy, consent

- Mark the route `noindex` unless the caller wants it found through search.
- Mark the options of a sensitive question, as the reference does with
  `data-quiz-private`, and add that selector to the recording block selector
  of the product's analytics, as the Egbe OS `egbe-os-analytics` skill describes.
- `validation.json` lists under `consent_geographies` the planned countries
  where tracking beyond what is strictly necessary needs consent. When the
  list is not empty, the route uses the product's consent mechanism for
  advertising pixels and session recording. When the product has none, add no
  pixel and report an open launch condition that names what runs on the
  route. A consent notice must leave the first screen and its controls
  usable.
- Install a channel's pixel only by following the Egbe OS skill of that
  channel.

## 8. Framework notes

- **Next.js App Router.** Add `src/app/<route>/page.tsx` as a server component
  that sets the page title and `robots`, and renders one client component that
  binds the engine. Import `quiz.public.json` and pass it to `createQuiz`; the
  types accept it without a cast.
- **Applications with their own server and a fallback to the application
  shell.** The fallback also answers the address of the quiz. Register the
  route explicitly and confirm that the deployed address shows the quiz.
- **Static hosting.** Publish the quiz as its own document at the route and
  confirm the host serves it at the address without a file extension. The
  first screen can be rendered into that document at build time from
  `quiz.public.json`, with the code that renders it in the browser; without
  that, the page stays empty until its module has loaded. One way is a module
  that describes a screen as a tree of tags, attributes, and texts: the
  browser turns the tree into elements, the build turns it into the text of
  the document. The rule for a tap before the module is ready applies then.

## 9. Boundaries

Do not change the homepage, pricing, navigation, signup, checkout, or product
behavior. Outside the route this workflow adds only what
[conversion-handoff.md](conversion-handoff.md) names: the endpoint of a request
form and the continuation after signup.

Run the application's relevant checks and build. Commit or deploy only when
that action is in scope, using the product's established release workflow and
`egbe-os-deploy`. A local implementation is not a claim of live verification.
