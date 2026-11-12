/**
 * Reference binding of the quiz engine to a plain page.
 *
 * It demonstrates the runtime behaviour: accepted first screen on load, automatic
 * advance, one button on multi-select and interstitial screens, a result before
 * the ask, the browser's own back, and canonical analytics delivery. The visual
 * design is deliberately plain; the product's own design replaces it.
 */
import { createQuiz } from "../engine/quiz-engine.mjs";
import { createQuizHistory } from "../engine/quiz-history.mjs";
import { replayEarlyActions } from "./quiz-early-actions.mjs";

/** How long a chosen option stays visible before the next screen appears. */
const ADVANCE_DELAY_MS = 180;
/** Taps this soon after a new screen are the tail of the previous tap. */
const TAP_GUARD_MS = 350;
/** How long the page waits for the browser to report a step back. */
const HISTORY_WAIT_MS = 1000;
const TRACKER_RETRY_MS = 500;
const TRACKER_RETRIES = 20;
const IDENTITY_FIELDS = [
  "visitor_id",
  "visit_id",
  "first_utm_source",
  "first_utm_medium",
  "first_utm_campaign",
];
const INPUT_TYPES = {
  name: { type: "text", autocomplete: "name" },
  email: { type: "email", autocomplete: "email" },
  phone: { type: "tel", autocomplete: "tel" },
  company: { type: "text", autocomplete: "organization" },
};

function readAttribution() {
  try {
    return window.__egbeAttribution?.read?.() ?? {};
  } catch {
    return {};
  }
}

/** Adds the visitor's identity and first-touch campaign fields to a descriptor. */
function withIdentity({ name, data }) {
  const attribution = readAttribution();
  const identity = {};
  for (const field of IDENTITY_FIELDS) {
    if (attribution[field]) identity[field] = attribution[field];
  }
  return { name, data: { ...data, ...identity } };
}

/**
 * Events wait here while the tracker is still loading. This binding sends
 * through `window.umami.track`, which exists only when the tracker is ready:
 * an event waits until then and is sent once.
 *
 * The runtime of the shared tracking snippet behaves differently. A product
 * that hands its events to `window.__egbeAttribution.track(name, data)` gets
 * `false` while the tracker is loading, but the runtime has kept the event
 * and sends it when the tracker is ready. Handing the event over again after
 * `false` sends it twice. With the runtime, hand an event over once, and keep
 * a queue like this one only while neither `window.__egbeAttribution` nor
 * `window.umami` exists.
 */
const pending = [];
let retries = 0;

function flush() {
  const send = window.umami?.track;
  if (typeof send !== "function") {
    if (pending.length > 0 && retries < TRACKER_RETRIES) {
      retries += 1;
      window.setTimeout(flush, TRACKER_RETRY_MS);
    }
    return;
  }
  while (pending.length > 0) {
    const { name, data } = pending.shift();
    send.call(window.umami, name, data);
  }
}

function track(event) {
  pending.push(withIdentity(event));
  flush();
}

function sessionStore() {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

function element(tag, properties = {}, children = []) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(properties)) {
    if (value === null || value === undefined || value === false) continue;
    if (name === "text") node.textContent = value;
    else if (name === "onClick") node.addEventListener("click", value);
    else node.setAttribute(name, value === true ? "" : String(value));
  }
  node.append(...children);
  return node;
}

/**
 * Canonical payload fields as `data-umami-event-*` attributes of a link. The
 * tracker sends the keys as the attributes spell them, in kebab-case
 * (`cta-id`), and adds nothing to them.
 */
function eventAttributes({ name, data }) {
  const attributes = { "data-umami-event": name };
  for (const [field, value] of Object.entries(data)) {
    attributes[`data-umami-event-${field.replaceAll("_", "-")}`] = value;
  }
  return attributes;
}

function pointList(points) {
  if (points.length === 0) return [];
  return [
    element(
      "ul",
      { class: "quiz-points" },
      points.map((point) => element("li", { text: point })),
    ),
  ];
}

function image(media) {
  if (!media) return [];
  return [element("img", { class: "quiz-media", src: media.src, alt: media.alt, loading: "lazy" })];
}

function proofList(proof) {
  if (proof.length === 0) return [];
  const items = proof.map((entry) => {
    const parts = [element("span", { text: entry.text })];
    if (entry.author) parts.push(element("cite", { text: entry.author }));
    if (entry.citation) parts.push(element("small", { text: entry.citation }));
    return element("li", {}, parts);
  });
  return [element("ul", { class: "quiz-proof" }, items)];
}

export function mountQuiz(root, spec) {
  const active = document.activeElement;
  const focusedOption = active && root.contains(active) ? active.closest("[data-option-id]") : null;
  const focusedScreenId = focusedOption?.closest("[data-quiz-screen]")?.dataset.quizScreen;
  const focusedOptionId = focusedOption?.dataset.optionId;
  root.__quizStopCapture?.();
  const earlyActions = root.__quizEarlyActions ?? [];
  delete root.__quizEarlyActions;
  delete root.__quizStopCapture;
  const quiz = createQuiz(spec, { storage: sessionStore(), onEvent: track });
  const history = createQuizHistory(window.history, spec.quiz_slug);
  const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  let locked = false;
  let acceptAfter = 0;
  let awaitedStep = 0;
  let steps = 0;
  let requestSent = false;
  let rendered = false;

  root.lang = spec.language;
  document.title = spec.title;

  /**
   * True when a tap may act: no advance is under way, the browser is not
   * stepping back, and the screen has settled.
   */
  function ready() {
    return !locked && awaitedStep === 0 && performance.now() >= acceptAfter;
  }

  function forward(view, fromIndex) {
    if (view.index !== fromIndex) history.forward(view.index);
    show(view);
  }

  function goBack() {
    if (!ready()) return;
    if (history.back()) {
      // The browser reports the step to `followHistory`. Until then a second
      // press must not step back once more.
      const step = ++steps;
      awaitedStep = step;
      window.setTimeout(() => {
        if (awaitedStep === step) awaitedStep = 0;
      }, HISTORY_WAIT_MS);
      return;
    }
    const view = quiz.back();
    history.replace(view.index);
    show(view);
  }

  function followHistory(event) {
    const index = history.follow(event.state);
    if (index === null) return;
    locked = false;
    awaitedStep = 0;
    show(quiz.goTo(index));
  }

  window.addEventListener("popstate", followHistory);

  function topBar(view) {
    const fill = element("span", { style: `width:${Math.round((view.index / view.total) * 100)}%` });
    return element("div", { class: "quiz-top" }, [
      element("button", {
        type: "button",
        class: "quiz-back",
        "data-quiz-back": true,
        "aria-label": spec.ui.back,
        hidden: !view.canGoBack || requestSent,
        text: "←",
        onClick: goBack,
      }),
      element(
        "div",
        {
          class: "quiz-progress",
          role: "progressbar",
          "aria-label": view.atResult ? spec.title : view.progressLabel,
          "aria-valuemin": 0,
          "aria-valuemax": view.total,
          "aria-valuenow": view.index,
        },
        [fill],
      ),
    ]);
  }

  function headline(text) {
    return element("h1", { class: "quiz-headline", id: "quiz-headline", tabindex: -1, text });
  }

  function question(view) {
    const { screen } = view;
    const multi = screen.select === "multi";
    const proceed = multi
      ? element("button", {
          type: "button",
          class: "quiz-continue",
          disabled: !view.canAdvance,
          text: screen.button,
          onClick: () => {
            if (ready()) forward(quiz.advance(screen.id), view.index);
          },
        })
      : null;
    const options = element(
      "div",
      {
        class: "quiz-options",
        role: "group",
        "aria-labelledby": "quiz-headline",
        // The session recorder is configured to leave these elements out.
        "data-quiz-private": Boolean(screen.sensitive),
      },
      screen.options.map((option) =>
        element("button", {
          type: "button",
          class: "quiz-option",
          "data-option-id": option.id,
          "aria-pressed": view.selected.includes(option.id) ? "true" : "false",
          text: option.label,
          onClick: (event) =>
            multi ? toggle(screen, option.id, options, proceed) : choose(event, screen, option.id),
        }),
      ),
    );
    const parts = [];
    if (screen.lead) parts.push(element("p", { class: "quiz-lead", text: screen.lead }));
    parts.push(headline(screen.headline));
    if (screen.hint) parts.push(element("p", { class: "quiz-hint", text: screen.hint }));
    parts.push(options);
    if (proceed) parts.push(proceed);
    return parts;
  }

  /** Switching an option changes the pressed states in place: focus and scroll stay. */
  function toggle(screen, optionId, options, proceed) {
    if (!ready()) return;
    const view = quiz.toggle(optionId, screen.id);
    for (const button of options.querySelectorAll("[data-option-id]")) {
      const pressed = view.selected.includes(button.dataset.optionId);
      button.setAttribute("aria-pressed", pressed ? "true" : "false");
    }
    proceed.disabled = !view.canAdvance;
  }

  function choose(event, screen, optionId) {
    if (!ready()) return;
    locked = true;
    const fromIndex = quiz.snapshot().index;
    for (const button of event.currentTarget.parentNode.querySelectorAll("[data-option-id]")) {
      button.setAttribute("aria-pressed", button === event.currentTarget ? "true" : "false");
    }
    window.setTimeout(
      () => {
        if (!locked) return; // The visitor left this screen through the browser's back.
        forward(quiz.select(optionId, screen.id), fromIndex);
      },
      reducedMotion ? 0 : ADVANCE_DELAY_MS,
    );
  }

  function interstitial(view) {
    const { screen } = view;
    const parts = [headline(screen.headline)];
    if (screen.body) parts.push(element("p", { class: "quiz-body", text: screen.body }));
    parts.push(
      ...image(screen.media),
      ...pointList(screen.points),
      ...proofList(screen.proof),
      element("button", {
        type: "button",
        class: "quiz-continue",
        text: screen.button,
        onClick: () => {
          if (ready()) forward(quiz.advance(screen.id), view.index);
        },
      }),
    );
    return parts;
  }

  function result() {
    const outcome = quiz.result();
    const parts = [
      headline(outcome.headline),
      ...pointList(outcome.points),
      element("p", { class: "quiz-body", text: outcome.body }),
      ...image(outcome.media),
      ...proofList(outcome.proof),
    ];
    const cta = quiz.cta(readAttribution());
    if (!cta) return parts;
    const note = cta.note ? [element("p", { class: "quiz-cta-note", text: cta.note })] : [];
    if (cta.destination.kind === "lead_form") {
      const holder = element("div", { class: "quiz-ask" });
      holder.append(
        element("button", {
          type: "button",
          class: "quiz-cta",
          text: cta.label,
          onClick: () => {
            if (!ready()) return;
            track(cta.event);
            holder.replaceChildren(leadForm(cta.destination));
            holder.querySelector("input")?.focus();
          },
        }),
        ...note,
      );
      parts.push(holder);
    } else {
      // A link with declarative attributes lets the tracker finish before the page leaves.
      parts.push(
        element("a", {
          class: "quiz-cta",
          href: cta.destination.href,
          rel: cta.destination.href.startsWith("/") ? null : "noopener",
          text: cta.label,
          ...eventAttributes(withIdentity(cta.event)),
        }),
        ...note,
      );
    }
    return parts;
  }

  function leadForm(destination) {
    const surface = { product_slug: spec.product_slug, path: spec.route, surface: "quiz_lead_form" };
    const alert = element("p", { class: "quiz-error", role: "alert", hidden: true });
    const submit = element("button", { type: "submit", class: "quiz-cta", text: destination.submitLabel });
    const fields = destination.fields.map((field) =>
      element("label", { class: "quiz-field" }, [
        element("span", { text: destination.fieldLabels[field] }),
        element("input", { name: field, required: true, ...INPUT_TYPES[field] }),
      ]),
    );
    const form = element("form", { class: "quiz-lead-form" }, [
      ...fields,
      ...(destination.consentNote
        ? [element("p", { class: "quiz-note", text: destination.consentNote })]
        : []),
      alert,
      submit,
    ]);
    track({ name: "signup_started", data: surface });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (submit.disabled) return;
      submit.disabled = true;
      alert.hidden = true;
      track({ name: "signup_submitted", data: surface });
      try {
        const contact = Object.fromEntries(new FormData(form));
        const response = await fetch(destination.action, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...destination.payload, contact }),
        });
        if (!response.ok) throw new Error(`the request failed with ${response.status}`);
        const data = await response.json().catch(() => ({}));
        // The product confirms the stored request; the browser delivers the event.
        if (data.analytics?.name) track({ name: data.analytics.name, data: data.analytics.data ?? {} });
        requestSent = true;
        root.querySelector("[data-quiz-back]").hidden = true;
        const received = element("h2", { tabindex: -1, text: destination.success.headline });
        form.replaceWith(
          element("div", { class: "quiz-success", role: "status" }, [
            received,
            element("p", { text: destination.success.body }),
          ]),
        );
        received.focus();
      } catch {
        alert.textContent = destination.error;
        alert.hidden = false;
        submit.disabled = false;
      }
    });
    return form;
  }

  function show(view, isTransition = rendered) {
    let parts;
    if (view.atResult) parts = result();
    else if (view.screen.type === "question") parts = question(view);
    else parts = interstitial(view);
    root.replaceChildren(
      topBar(view),
      element(
        "section",
        { class: "quiz-screen", "data-quiz-screen": view.atResult ? "result" : view.screen.id },
        parts,
      ),
    );
    locked = false;
    // Early SSR actions are transitions too; plain first paint must not steal focus.
    if (isTransition) {
      acceptAfter = performance.now() + TAP_GUARD_MS;
      root.querySelector("#quiz-headline")?.focus();
    }
    rendered = true;
  }

  const first = quiz.snapshot();
  history.mount(first.index);
  const resumed = replayEarlyActions(quiz, earlyActions);
  if (resumed.index !== first.index) history.forward(resumed.index);
  show(resumed, resumed.index !== first.index);
  // Same-screen hydration replaces the SSR nodes, not the visitor's focus.
  if (resumed.index === first.index && resumed.screen?.id === focusedScreenId) {
    for (const option of root.querySelectorAll("[data-option-id]")) {
      if (option.dataset.optionId === focusedOptionId) option.focus({ preventScroll: true });
    }
  }
  return {
    quiz,
    /** Call when the page removes the quiz without leaving the document. */
    unmount() {
      window.removeEventListener("popstate", followHistory);
      root.replaceChildren();
    },
  };
}

const root = typeof document === "undefined" ? null : document.querySelector("[data-quiz]");
const embedded = root && document.getElementById(root.dataset.quiz);
if (embedded) mountQuiz(root, JSON.parse(embedded.textContent));
