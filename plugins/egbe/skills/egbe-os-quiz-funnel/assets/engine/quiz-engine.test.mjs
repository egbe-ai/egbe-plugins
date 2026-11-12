import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { PUBLIC_CONTRACT, createQuiz } from "./quiz-engine.mjs";

const example = JSON.parse(
  await readFile(
    new URL("../examples/egbe-docs/product/quizzes/books-checkup/quiz.public.json", import.meta.url),
    "utf8",
  ),
);

const DEFAULT_ANSWERS = {
  role: "freelancer",
  behind: "many",
  tracking: "sheet",
  worries: ["deadline"],
  volume: "mid",
  penalty: "no",
};

function spec(changes = {}) {
  return { ...structuredClone(example), ...changes };
}

function screenOf(quizSpec, id) {
  return quizSpec.screens.find((screen) => screen.id === id);
}

function memoryStorage(initial = {}) {
  const items = new Map(Object.entries(initial));
  return {
    getItem: (key) => (items.has(key) ? items.get(key) : null),
    setItem: (key, value) => items.set(key, String(value)),
    removeItem: (key) => items.delete(key),
    items,
  };
}

function recorder() {
  const events = [];
  return { events, onEvent: (event) => events.push(event) };
}

/** Answer screens until `stop` is the current screen, or until the result. */
function walk(quiz, answers = {}, stop = null) {
  const chosen = { ...DEFAULT_ANSWERS, ...answers };
  while (!quiz.snapshot().atResult && quiz.snapshot().screen.id !== stop) {
    const { screen } = quiz.snapshot();
    if (screen.type === "interstitial") {
      quiz.advance();
    } else if (screen.select === "multi") {
      for (const optionId of chosen[screen.id]) quiz.toggle(optionId);
      quiz.advance();
    } else {
      quiz.select(chosen[screen.id]);
    }
  }
  return quiz;
}

test("rejects a specification of another contract", () => {
  assert.throws(() => createQuiz({ contract: "something-else" }), /quiz-funnel-public-v1/);
  assert.throws(() => createQuiz(spec({ screens: [] })), /no screens/);
  assert.throws(() => createQuiz(spec({ results: [] })), /no results/);
  assert.equal(example.contract, PUBLIC_CONTRACT);
});

test("opens on the first question and advances on a single choice", () => {
  const { events, onEvent } = recorder();
  const quiz = createQuiz(spec(), { onEvent });

  const first = quiz.snapshot();
  assert.equal(first.index, 0);
  assert.equal(first.screen.id, "role");
  assert.equal(first.screen.type, "question");
  assert.equal(first.screen.lead, "Find out what your books need before tax season.");
  assert.equal(first.canGoBack, false);
  assert.equal(first.canAdvance, false);
  assert.equal(first.progressLabel, "Step 1 of 8");

  const second = quiz.select("studio");
  assert.equal(second.screen.id, "behind");
  assert.equal(second.position, 2);
  assert.deepEqual(events, [
    {
      name: "button_click",
      data: {
        product_slug: "example-books",
        path: "/quiz/books-checkup",
        surface: "quiz",
        button_id: "role.studio",
        button_role: "quiz_answer",
        position: 1,
      },
    },
  ]);
});

test("refuses unknown options and the wrong kind of step", () => {
  const quiz = createQuiz(spec());
  assert.throws(() => quiz.select("nobody"), /no option nobody/);
  assert.throws(() => quiz.advance(), /advances through select/);
  assert.throws(() => quiz.toggle("freelancer"), /not a multi-select question/);
});

test("a tap that arrives after the screen has changed is ignored", () => {
  const { events, onEvent } = recorder();
  const quiz = createQuiz(spec(), { onEvent });
  quiz.select("studio", "role");
  events.length = 0;

  // A second tap meant for the first screen lands while the second is shown.
  assert.equal(quiz.select("few", "role").screen.id, "behind");
  assert.equal(quiz.toggle("few", "worries").screen.id, "behind");
  assert.equal(quiz.advance("halfway").screen.id, "behind");
  assert.deepEqual(quiz.answers(), { role: ["studio"] });
  assert.deepEqual(events, []);

  assert.equal(quiz.select("few", "behind").screen.id, "tracking");
});

test("a multi-select question needs a choice and reports it in option order", () => {
  const { events, onEvent } = recorder();
  const quiz = walk(createQuiz(spec(), { onEvent }), {}, "worries");
  events.length = 0;

  const screen = quiz.snapshot();
  assert.equal(screen.screen.hint, "Choose all that apply.");
  assert.equal(screen.canAdvance, false);
  assert.throws(() => quiz.advance(), /needs at least one option/);

  quiz.toggle("audit");
  quiz.toggle("deadline");
  quiz.toggle("cashflow");
  assert.deepEqual(quiz.toggle("cashflow").selected, ["audit", "deadline"]);
  assert.equal(quiz.snapshot().canAdvance, true);
  assert.deepEqual(events, [], "switching an option is not an analytics event");

  assert.equal(quiz.advance().screen.id, "volume");
  assert.equal(events.length, 1);
  assert.equal(events[0].data.button_id, "worries.continue");
  assert.equal(events[0].data.button_role, "quiz_answer");
  assert.equal(events[0].data.state, "deadline+audit");
});

test("an escape option excludes the other options of a multi-select question", () => {
  const quiz = walk(createQuiz(spec()), {}, "worries");
  quiz.toggle("deadline");
  assert.deepEqual(quiz.toggle("nothing").selected, ["nothing"]);
  assert.deepEqual(quiz.toggle("audit").selected, ["audit"]);
});

test("the answer to a sensitive question stays on the page", () => {
  const { events, onEvent } = recorder();
  const quiz = walk(createQuiz(spec(), { onEvent }), {}, "penalty");
  events.length = 0;

  assert.equal(quiz.snapshot().screen.sensitive, true);
  quiz.select("yes");
  assert.equal(events[0].data.button_id, "penalty.answered");
  assert.deepEqual(quiz.answers().penalty, ["yes"], "the page itself keeps the answer");

  const multi = spec();
  screenOf(multi, "worries").sensitive = true;
  const second = recorder();
  const sensitive = walk(createQuiz(multi, { onEvent: second.onEvent }), {}, "volume");
  const confirmed = second.events.at(-1).data;
  assert.equal(confirmed.button_id, "worries.continue");
  assert.equal("state" in confirmed, false);
  assert.deepEqual(sensitive.answers().worries, ["deadline"]);
});

test("an interstitial screen shows its own texts or the first matching variant", () => {
  const { events, onEvent } = recorder();
  const plain = walk(createQuiz(spec(), { onEvent }), { behind: "few" }, "halfway");
  assert.deepEqual(plain.snapshot().screen, {
    id: "halfway",
    type: "interstitial",
    kind: "encouragement",
    headline: "You are halfway there",
    points: [],
    proof: [],
    media: null,
    button: "Continue",
    body: "Three more answers and you will see what your books need first.",
  });
  assert.equal(plain.snapshot().canAdvance, true);

  events.length = 0;
  plain.advance();
  assert.deepEqual(events[0].data, {
    product_slug: "example-books",
    path: "/quiz/books-checkup",
    surface: "quiz",
    button_id: "halfway.continue",
    button_role: "quiz_continue",
    position: 4,
  });

  const adapted = walk(createQuiz(spec()), { behind: "year" }, "halfway").snapshot().screen;
  assert.equal(adapted.headline, "This is what a catch-up is for");
  assert.equal(
    adapted.body,
    "Books that are over a year behind can be reconciled month by month. " +
      "Three more answers and you will see where to start.",
  );
  assert.equal(adapted.button, "Continue");
  assert.equal("variants" in adapted, false);
  assert.equal("when" in adapted, false);
});

test("an interstitial screen lists the proof it shows", () => {
  const screen = walk(createQuiz(spec()), {}, "how").snapshot().screen;
  assert.deepEqual(screen.proof, [
    {
      id: "review-summary",
      kind: "fact",
      text: "The review takes 20 minutes and you keep the written summary.",
    },
    {
      id: "one-bookkeeper",
      kind: "fact",
      text: "One bookkeeper handles your books from the first month to the last.",
    },
  ]);

  const custom = spec();
  screenOf(custom, "how").variants = [
    {
      when: { any: [{ screen: "worries", any_of: ["audit"] }] },
      proof_ids: ["one-bookkeeper"],
      points: ["You named {{answer:worries}}"],
    },
  ];
  const varied = walk(createQuiz(custom), { worries: ["audit", "cashflow"] }, "how");
  assert.deepEqual(
    varied.snapshot().screen.proof.map((proof) => proof.id),
    ["one-bookkeeper"],
  );
  assert.deepEqual(varied.snapshot().screen.points, ["You named cash flow, an audit"]);
  assert.equal(varied.snapshot().screen.headline, "Here is how the review works");
});

test("back keeps the answers and stops at the first screen", () => {
  const quiz = createQuiz(spec());
  quiz.select("shop");
  quiz.select("few");

  const previous = quiz.back();
  assert.equal(previous.screen.id, "behind");
  assert.deepEqual(previous.selected, ["few"]);
  assert.equal(quiz.back().screen.id, "role");
  assert.equal(quiz.back().index, 0);
  assert.deepEqual(quiz.answers(), { role: ["shop"], behind: ["few"] });
});

test("the browser's back and forward reach only screens already reached", () => {
  const quiz = walk(createQuiz(spec()), {}, "worries");
  assert.equal(quiz.snapshot().index, 4);

  assert.equal(quiz.goTo(1).screen.id, "behind");
  assert.equal(quiz.goTo(4).screen.id, "worries", "forward to the furthest screen reached");
  assert.equal(quiz.goTo(5).screen.id, "worries", "not past an unanswered question");
  assert.equal(quiz.goTo(-1).screen.id, "worries");
  assert.equal(quiz.goTo(1.5).screen.id, "worries");
  assert.equal(quiz.goTo("2").screen.id, "worries");

  const finished = walk(createQuiz(spec()));
  assert.equal(finished.goTo(0).screen.id, "role");
  assert.equal(finished.goTo(8).atResult, true);
});

test("there is no result before the answers decide it", () => {
  const quiz = createQuiz(spec());
  quiz.select("freelancer");
  assert.equal(quiz.result(), null);
  assert.equal(quiz.cta(), null);
  quiz.select("current");
  assert.equal(quiz.result(), null, "the tracking answer can still change the result");
});

test("a not-fit result appears as soon as the answers decide it", () => {
  const { events, onEvent } = recorder();
  const quiz = createQuiz(spec(), { onEvent });
  quiz.select("freelancer");
  quiz.select("current");
  const view = quiz.select("app");

  assert.equal(view.atResult, true, "the remaining questions would not change it");
  assert.equal(view.index, example.screens.length);
  assert.equal(quiz.result().id, "in-shape");
  assert.equal(quiz.cta().event.data.cta_role, "alternative");
  assert.deepEqual(
    events.map((event) => [event.data.button_id, event.data.position]),
    [["role.freelancer", 1], ["behind.current", 2], ["tracking.app", 3]],
  );
});

test("a fit or partial result waits for every question", () => {
  // Nothing after "behind" can turn these answers into a not-fit result, but
  // the fitting results quote later answers: the visitor answers them all.
  const quiz = createQuiz(spec());
  quiz.select("freelancer");
  assert.equal(quiz.select("few").screen.id, "tracking");
  assert.equal(quiz.select("sheet").screen.id, "halfway");
});

test("an earlier result that a later answer can still reach keeps the questions coming", () => {
  const custom = spec();
  custom.results = [
    { id: "busy", fit: "fit", when: { all: [{ screen: "volume", any_of: ["high"] }] }, headline: "Busy", body: "Body", cta: { label: "Go" } },
    { id: "current", fit: "not_fit", when: { all: [{ screen: "behind", any_of: ["current"] }] }, headline: "Current", body: "Body", cta: null },
    { id: "rest", fit: "partial", headline: "Rest", body: "Body", cta: { label: "Go" } },
  ];
  const quiz = walk(createQuiz(custom), { behind: "current" }, "volume");
  assert.equal(quiz.snapshot().screen.id, "volume", "a high volume would still lead to busy");
  const view = quiz.select("low");
  assert.equal(view.atResult, true, "after the volume the not-fit result is decided");
  assert.equal(quiz.result().id, "current");
  assert.equal(quiz.back().screen.id, "volume");
});

test("back and the browser's history return to the deciding question, not to skipped screens", () => {
  const quiz = createQuiz(spec());
  quiz.select("freelancer");
  quiz.select("current");
  quiz.select("app");

  assert.equal(quiz.goTo(3).atResult, true, "the interstitial after the deciding question is skipped");
  assert.equal(quiz.goTo(7).atResult, true);
  const back = quiz.back();
  assert.equal(back.screen.id, "tracking");
  assert.deepEqual(back.selected, ["app"]);
  assert.equal(quiz.goTo(example.screens.length).atResult, true, "forward to the result again");
  assert.equal(quiz.goTo(1).screen.id, "behind");

  // Another answer to the deciding question continues with the remaining screens.
  quiz.goTo(2);
  assert.equal(quiz.select("sheet").screen.id, "halfway");
  assert.equal(quiz.goTo(3).screen.id, "halfway");
});

test("an early result quotes only the answers that decided it", () => {
  const custom = spec();
  const inShape = custom.results.find((result) => result.id === "in-shape");
  inShape.headline = "Books {{answer:behind}}";
  inShape.points = ["Invoices a month: {{answer:volume}}", "Tracked with {{answer:tracking}}"];

  // A full path first, then back to the tracking question and a deciding answer.
  const quiz = walk(createQuiz(custom), { behind: "current", tracking: "sheet", volume: "high" });
  assert.equal(quiz.result().id, "review");
  quiz.goTo(2);
  quiz.select("app");
  const result = quiz.result();
  assert.equal(result.id, "in-shape");
  assert.equal(result.headline, "Books up to date");
  assert.deepEqual(result.points, ["Tracked with an accounting app"], "the old volume answer is not quoted");
});

test("a not-fit result that quotes a later answer in a sentence waits for it", () => {
  const custom = spec();
  custom.results.find((result) => result.id === "in-shape").body = "About {{answer:volume}} invoices a month.";
  const quiz = createQuiz(custom);
  quiz.select("freelancer");
  quiz.select("current");
  assert.equal(quiz.select("app").screen.id, "halfway", "the sentence would break without the volume");
  const finished = walk(quiz, { behind: "current", tracking: "app" });
  assert.equal(finished.result().body, "About 10 to 50 invoices a month.");
});

test("a reload keeps an early result, and a saved later screen shows it", () => {
  const storage = memoryStorage();
  const quiz = createQuiz(spec(), { storage });
  quiz.select("freelancer");
  quiz.select("current");
  quiz.select("app");
  const reloaded = createQuiz(spec(), { storage });
  assert.equal(reloaded.snapshot().atResult, true);
  assert.equal(reloaded.result().id, "in-shape");
  assert.equal(reloaded.back().screen.id, "tracking");

  const key = "quiz-funnel:books-checkup";
  const answers = { role: ["freelancer"], behind: ["current"], tracking: ["app"] };
  const later = memoryStorage({ [key]: JSON.stringify({ version: example.public_sha256, index: 4, answers }) });
  assert.equal(createQuiz(spec(), { storage: later }).snapshot().atResult, true);
});

test("too many remaining answers leave the decision to the last screen", () => {
  const custom = spec();
  const many = (id) => ({
    id,
    type: "question",
    select: "multi",
    headline: "Pick",
    hint: "Choose all that apply.",
    button: "Continue",
    options: Array.from({ length: 11 }, (_, n) => ({ id: `o${n}`, label: `Option ${n}` })),
  });
  custom.screens.push(many("first"), many("second"));
  custom.results.unshift({
    id: "picky",
    fit: "fit",
    when: { all: [{ screen: "first", any_of: ["o1"] }, { screen: "second", any_of: ["o1"] }] },
    headline: "Picky",
    body: "Body",
    cta: { label: "Go" },
  });
  custom.results.find((result) => result.id === "in-shape").when.all.push({ screen: "first", none_of: ["o0"] });
  const quiz = createQuiz(custom);
  quiz.select("freelancer");
  quiz.select("current");
  assert.equal(quiz.select("app").screen.id, "halfway", "2^11 x 2^11 combinations are too many to be sure");
});

test("the first matching result wins and the last one is the default", () => {
  const cases = [
    [{ behind: "many", volume: "high" }, "planned-catch-up"],
    [{ behind: "year", volume: "low" }, "catch-up"],
    [{ behind: "few" }, "tidy-up"],
    [{ behind: "current", tracking: "app" }, "in-shape"],
    [{ behind: "current", tracking: "sheet" }, "review"],
  ];
  for (const [answers, expected] of cases) {
    const quiz = walk(createQuiz(spec()), answers);
    assert.equal(quiz.result().id, expected, JSON.stringify(answers));
  }
});

test("conditions support any, none_of, and multi-select answers", () => {
  const custom = spec();
  custom.results = [
    {
      id: "worried",
      fit: "fit",
      when: {
        any: [
          { screen: "worries", any_of: ["audit"] },
          { screen: "volume", any_of: ["high"] },
        ],
      },
      headline: "Worried",
      body: "Body",
      cta: { label: "Go" },
    },
    {
      id: "calm",
      fit: "partial",
      when: { all: [{ screen: "worries", none_of: ["deadline", "audit"] }] },
      headline: "Calm",
      body: "Body",
      cta: { label: "Go" },
    },
    { id: "rest", fit: "partial", headline: "Rest", body: "Body", cta: { label: "Go" } },
  ];

  const pick = (answers) => walk(createQuiz(custom), answers).result().id;
  assert.equal(pick({ worries: ["cashflow", "audit"], volume: "low" }), "worried");
  assert.equal(pick({ worries: ["cashflow"], volume: "high" }), "worried");
  assert.equal(pick({ worries: ["cashflow"], volume: "low" }), "calm");
  assert.equal(pick({ worries: ["nothing"], volume: "low" }), "calm");
  assert.equal(pick({ worries: ["deadline"], volume: "low" }), "rest");
});

test("a sentence quotes the answer in its sentence form", () => {
  const review = walk(createQuiz(spec()), { behind: "current", tracking: "bank" }).result();
  assert.match(review.body, /tracking expenses with bank statements only can cost you time/);
  assert.doesNotMatch(review.body, /\{\{/);

  const unphrased = spec();
  delete screenOf(unphrased, "tracking").options[2].phrase;
  const fallback = walk(createQuiz(unphrased), { behind: "current", tracking: "bank" }).result();
  assert.match(fallback.body, /tracking expenses with Bank statements only can cost/);
});

test("points quote any answer and drop what the visitor declined", () => {
  const full = walk(createQuiz(spec()), {
    behind: "current",
    role: "shop",
    volume: "mid",
    worries: ["audit", "deadline"],
  }).result();
  assert.deepEqual(full.points, [
    "Your business: online shop",
    "Invoices a month: 10 to 50",
    "On your mind: the tax deadline, an audit",
  ]);

  const declined = walk(createQuiz(spec()), {
    behind: "current",
    role: "other",
    worries: ["nothing"],
  }).result();
  assert.deepEqual(declined.points, ["Invoices a month: 10 to 50"]);

  const none = spec();
  delete none.results.at(-1).points;
  assert.deepEqual(walk(createQuiz(none), { behind: "current" }).result().points, []);
});

test("a result lists the proof it shows", () => {
  const custom = spec();
  custom.results.at(-1).proof_ids = ["review-summary"];
  const result = walk(createQuiz(custom), { behind: "current" }).result();
  assert.deepEqual(result.proof, [
    {
      id: "review-summary",
      kind: "fact",
      text: "The review takes 20 minutes and you keep the written summary.",
    },
  ]);
});

test("screens and results pass their image on", () => {
  const custom = spec();
  const sample = { src: "/quiz/books-checkup/summary.png", alt: "A written summary" };
  const close = { src: "https://cdn.example.com/close.png", alt: "A monthly close" };
  screenOf(custom, "how").media = sample;
  screenOf(custom, "halfway").variants[0].media = close;
  custom.results.at(-1).media = sample;

  assert.equal(walk(createQuiz(custom), { behind: "few" }, "halfway").snapshot().screen.media, null);
  assert.deepEqual(
    walk(createQuiz(custom), { behind: "year" }, "halfway").snapshot().screen.media,
    close,
  );
  assert.deepEqual(walk(createQuiz(custom), {}, "how").snapshot().screen.media, sample);
  assert.deepEqual(walk(createQuiz(custom), { behind: "current" }).result().media, sample);
  assert.equal(walk(createQuiz(custom)).result().media, null);
});

test("a call to action carries the note that is shown under it", () => {
  const quiz = walk(createQuiz(spec()));
  assert.equal(quiz.cta().note, "The call takes 20 minutes. You keep the written summary.");

  const other = walk(createQuiz(spec()), { behind: "current", tracking: "app" });
  assert.equal(other.cta().note, null);
});

test("a booking link keeps its own parameters and carries the first touch", () => {
  const custom = spec();
  custom.goal.destination.url = "https://cal.example.com/books-review?utm_medium=partner&seat=2";
  const quiz = walk(createQuiz(custom));

  const { destination, event, label } = quiz.cta({
    first_utm_source: "meta",
    first_utm_medium: "paid_social",
    first_utm_campaign: " spring ",
    first_utm_content: "ad-7",
    first_fbclid: "click-1",
    email: "person@example.com",
  });
  const params = new URL(destination.href).searchParams;

  assert.equal(label, "Book the free review");
  assert.equal(destination.kind, "booking_url");
  assert.equal(destination.href.split("?")[0], "https://cal.example.com/books-review");
  assert.equal(params.get("seat"), "2");
  assert.equal(params.get("utm_medium"), "partner", "the address keeps its own value");
  assert.equal(params.get("utm_source"), "meta");
  assert.equal(params.get("utm_campaign"), "spring");
  assert.equal(
    params.get("utm_content"),
    "books-checkup.catch-up",
    "the result parameter is always delivered",
  );
  assert.doesNotMatch(destination.href, /person|click-1|ad-7/);
  assert.deepEqual(event, {
    name: "cta_click",
    data: {
      product_slug: "example-books",
      path: "/quiz/books-checkup",
      surface: "quiz_result",
      cta_id: "catch-up",
      cta_role: "call_primary",
      label: "Book the free review",
      destination: "https://cal.example.com/books-review",
    },
  });
});

test("fallback parameters describe only a visitor without a campaign", () => {
  const quiz = walk(createQuiz(spec()));

  const direct = new URL(quiz.cta().destination.href).searchParams;
  assert.equal(direct.get("utm_source"), "quiz");
  assert.equal(direct.get("utm_campaign"), "books-checkup");
  assert.equal(direct.get("utm_content"), "books-checkup.catch-up");

  const paid = new URL(quiz.cta({ first_utm_source: "reddit" }).destination.href).searchParams;
  assert.equal(paid.get("utm_source"), "reddit");
  assert.equal(paid.has("utm_campaign"), false, "no invented campaign for a real source");
  assert.equal(paid.get("utm_content"), "books-checkup.catch-up");
});

test("the result is left out of the link unless a parameter is named for it", () => {
  const custom = spec();
  delete custom.goal.destination.result_param;
  delete custom.goal.destination.fallback_params;
  const quiz = walk(createQuiz(custom));
  assert.equal(quiz.cta().destination.href, "https://cal.example.com/books-review");
  assert.equal(
    quiz.cta({ first_utm_content: "ad-7" }).destination.href,
    "https://cal.example.com/books-review?utm_content=ad-7",
  );
});

test("signup and checkout destinations stay on the product origin", () => {
  const signup = spec();
  signup.goal = { type: "signup", destination: { kind: "signup", path: "/signup?next=/dashboard" } };
  const signupCta = walk(createQuiz(signup)).cta({ first_utm_source: "meta" });
  assert.deepEqual(signupCta.destination, { kind: "signup", href: "/signup?next=/dashboard" });
  assert.equal(signupCta.event.data.cta_role, "signup_primary");
  assert.equal(signupCta.event.data.destination, "/signup");

  const checkout = spec();
  checkout.goal = {
    type: "payment",
    destination: {
      kind: "checkout",
      path: "/checkout",
      plan_key: "pro monthly",
      price: "$95 per month",
    },
  };
  const checkoutCta = walk(createQuiz(checkout)).cta();
  assert.deepEqual(checkoutCta.destination, {
    kind: "checkout",
    href: "/checkout?plan=pro%20monthly",
  });
  assert.equal(checkoutCta.event.data.cta_role, "checkout_primary");

  checkout.goal.destination = {
    kind: "checkout",
    path: "/checkout?ref=quiz",
    plan_key: "pro",
    price: "$95 per month",
    plan_param: "tier",
  };
  assert.equal(walk(createQuiz(checkout)).cta().destination.href, "/checkout?ref=quiz&tier=pro");
});

test("a request form receives the shareable answers and the first touch", () => {
  const lead = spec();
  lead.goal = {
    type: "call",
    destination: {
      kind: "lead_form",
      action: "/api/lead",
      fields: ["name", "email"],
      field_labels: { name: "Name", email: "Work email" },
      submit_label: "Request the review",
      error: "We could not send your request. Please try again.",
      success: { headline: "Request received", body: "We will reply within one working day." },
    },
  };
  const { destination, event } = walk(createQuiz(lead), { penalty: "yes" }).cta({
    visitor_id: "v-1",
    first_utm_source: "meta",
    unknown: "dropped",
  });

  assert.equal(destination.kind, "lead_form");
  assert.equal(destination.action, "/api/lead");
  assert.deepEqual(destination.fields, ["name", "email"]);
  assert.equal(destination.consentNote, null);
  assert.deepEqual(destination.payload, {
    quiz_slug: "books-checkup",
    result_id: "catch-up",
    answers: {
      role: ["freelancer"],
      behind: ["many"],
      tracking: ["sheet"],
      worries: ["deadline"],
      volume: ["mid"],
    },
    attribution: { visitor_id: "v-1", first_utm_source: "meta" },
  });
  assert.equal(event.data.destination, "/api/lead");
});

test("a not-fit result leads to its own destination or to none", () => {
  const quiz = walk(createQuiz(spec()), { behind: "current", tracking: "app" });
  assert.equal(quiz.result().fit, "not_fit");
  const { destination, event } = quiz.cta({ first_utm_source: "meta" });
  assert.deepEqual(destination, { kind: "link", href: "/guides/monthly-close" });
  assert.equal(event.data.cta_role, "alternative");

  const silent = spec();
  silent.results[0].cta = null;
  const none = walk(createQuiz(silent), { behind: "current", tracking: "app" });
  assert.equal(none.result().hasCta, false);
  assert.equal(none.cta(), null);
});

test("progress survives a reload and a changed page starts over", () => {
  const storage = memoryStorage();
  const first = createQuiz(spec(), { storage });
  first.select("studio");
  first.select("year");

  const reloaded = createQuiz(spec(), { storage });
  assert.equal(reloaded.snapshot().screen.id, "tracking");
  assert.deepEqual(reloaded.answers(), { role: ["studio"], behind: ["year"] });

  const notes = createQuiz(spec({ spec_sha256: "edited-internal-notes" }), { storage });
  assert.equal(notes.snapshot().screen.id, "tracking", "only a change of the page resets");

  const changed = createQuiz(spec({ public_sha256: "another" }), { storage });
  assert.equal(changed.snapshot().index, 0);
  assert.deepEqual(changed.answers(), {});
});

test("a finished quiz restores its result for the product to continue", () => {
  const storage = memoryStorage();
  walk(createQuiz(spec(), { storage }), { behind: "few" });
  assert.equal(createQuiz(spec(), { storage }).result().id, "tidy-up");
});

test("damaged saved state is ignored", () => {
  const key = "quiz-funnel:books-checkup";
  const version = example.public_sha256;
  const damaged = [
    "not json",
    JSON.stringify({ version, index: 99, answers: {} }),
    JSON.stringify({ version, index: 2, answers: { role: ["freelancer"] } }),
    JSON.stringify({ version, index: 1, answers: { role: ["nobody"] } }),
    JSON.stringify({ version, index: 1, answers: { role: ["freelancer", "studio"] } }),
    JSON.stringify({ version, index: 1, answers: { role: ["freelancer", "freelancer"] } }),
    JSON.stringify({ version, index: 1, answers: { invented: ["x"] } }),
    JSON.stringify({ version, index: 1, answers: [] }),
    JSON.stringify({ version, index: "1", answers: { role: ["freelancer"] } }),
  ];
  for (const value of damaged) {
    const quiz = createQuiz(spec(), { storage: memoryStorage({ [key]: value }) });
    assert.equal(quiz.snapshot().index, 0, value);
  }
});

test("blocked storage does not stop the quiz", () => {
  const blocked = {
    getItem: () => {
      throw new Error("blocked");
    },
    setItem: () => {
      throw new Error("blocked");
    },
    removeItem: () => {
      throw new Error("blocked");
    },
  };
  const quiz = createQuiz(spec(), { storage: blocked });
  assert.equal(quiz.select("freelancer").screen.id, "behind");
  assert.equal(quiz.restart().index, 0);
});

test("restart clears the answers and the saved state", () => {
  const storage = memoryStorage();
  const quiz = walk(createQuiz(spec(), { storage }));
  assert.equal(quiz.restart().screen.id, "role");
  assert.deepEqual(quiz.answers(), {});
  assert.equal(storage.items.size, 0);
});
