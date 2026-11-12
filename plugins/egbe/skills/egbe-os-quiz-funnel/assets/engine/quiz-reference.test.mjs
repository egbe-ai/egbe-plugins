import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import vm from "node:vm";
import { createQuiz } from "./quiz-engine.mjs";
import { renderFirstScreen } from "../reference/quiz-first-screen.mjs";
import { replayEarlyActions } from "../reference/quiz-early-actions.mjs";
import { mountQuiz } from "../reference/quiz-page.mjs";

const example = JSON.parse(await readFile(new URL("../examples/egbe-docs/product/quizzes/books-checkup/quiz.public.json", import.meta.url), "utf8"));
const intro = { id: "intro", type: "interstitial", kind: "teach", headline: '<Welcome & "hello">', body: "Here is the process.", button: "Begin" };
const withIntro = () => ({ ...structuredClone(example), screens: [intro, ...structuredClone(example.screens)] });

// Exercise the actual binding, including event handlers, focus and its clock.
// No browser dependency is needed for these DOM operations.
function mountedQuiz(t, spec, actions = [], { storage, reducedMotion = false, focusedOptionId } = {}) {
  let now = 100;
  let activeElement = null;
  const timers = [];
  class Element {
    constructor() { this.attributes = {}; this.children = []; this.handlers = {}; }
    setAttribute(name, value) { this.attributes[name] = value; }
    get dataset() {
      return Object.fromEntries(Object.entries(this.attributes).filter(([name]) => name.startsWith("data-"))
        .map(([name, value]) => [name.slice(5).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase()), value]));
    }
    append(...children) {
      for (const child of children) { child.parentNode = this; this.children.push(child); }
    }
    replaceChildren(...children) {
      if (this.contains(activeElement)) activeElement = null;
      for (const child of this.children) child.parentNode = null;
      this.children = []; this.append(...children);
    }
    contains(node) { return this === node || this.children.some((child) => child.contains(node)); }
    closest(selector) {
      return Object.hasOwn(this.attributes, selector.slice(1, -1)) ? this : this.parentNode?.closest(selector);
    }
    addEventListener(name, handler) { this.handlers[name] = handler; }
    querySelectorAll(selector) {
      const matches = (node) => selector.startsWith("#")
        ? node.attributes.id === selector.slice(1)
        : Object.hasOwn(node.attributes, selector.slice(1, -1));
      return this.children.flatMap((child) => [
        ...(matches(child) ? [child] : []), ...child.querySelectorAll(selector),
      ]);
    }
    querySelector(selector) { return this.querySelectorAll(selector)[0] ?? null; }
    focus() { activeElement = this; }
  }
  const globals = {
    document: { createElement: () => new Element(), title: "", get activeElement() { return activeElement; } },
    window: {
      history: {
        state: null,
        replaceState(state) { this.state = state; },
        pushState(state) { this.state = state; },
      },
      sessionStorage: storage,
      matchMedia: () => ({ matches: reducedMotion }),
      addEventListener() {}, removeEventListener() {},
      setTimeout(callback, delay) { timers.push({ callback, at: now + delay }); },
      umami: { track() {} },
    },
    performance: { now: () => now },
  };
  for (const [name, value] of Object.entries(globals)) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, { value, configurable: true });
    t.after(() => {
      if (previous) Object.defineProperty(globalThis, name, previous);
      else delete globalThis[name];
    });
  }
  const root = new Element();
  root.__quizEarlyActions = actions;
  if (focusedOptionId) {
    const screen = new Element();
    screen.setAttribute("data-quiz-screen", spec.screens[0].id);
    const option = new Element();
    option.setAttribute("data-option-id", focusedOptionId);
    screen.append(option);
    root.append(screen);
    option.focus();
  }
  const { quiz } = mountQuiz(root, spec);
  return {
    root, quiz,
    get focused() { return activeElement; },
    clickOption(optionId) {
      const button = optionId
        ? root.querySelectorAll("[data-option-id]").find((item) => item.dataset.optionId === optionId)
        : root.querySelector("[data-option-id]");
      button.handlers.click({ currentTarget: button });
    },
    tick(milliseconds) {
      const until = now + milliseconds;
      timers.sort((a, b) => a.at - b.at);
      while (timers.length && timers[0].at <= until) {
        const timer = timers.shift();
        now = timer.at;
        timer.callback();
        timers.sort((a, b) => a.at - b.at);
      }
      now = until;
    },
  };
}

for (const toggled of [false, true]) {
  test(`multi-select mount preserves the SSR-focused option (early toggle: ${toggled})`, (t) => {
    const spec = structuredClone(example);
    const question = spec.screens.find((screen) => screen.id === "worries");
    spec.screens = [question, ...spec.screens.filter((screen) => screen !== question)];
    const actions = toggled ? [{ kind: "toggle", screenId: "worries", optionId: "deadline" }] : [];
    const page = mountedQuiz(t, spec, actions, { focusedOptionId: "deadline" });
    const option = page.root.querySelectorAll("[data-option-id]").find((item) => item.dataset.optionId === "deadline");
    assert.equal(page.focused, option);
    assert.deepEqual(page.quiz.snapshot().selected, toggled ? ["deadline"] : []);
    page.clickOption("deadline");
    assert.deepEqual(page.quiz.snapshot().selected, toggled ? [] : ["deadline"]);
    assert.equal(page.focused, option, "subsequent keyboard toggles keep focus in place");
  });
}

for (const reducedMotion of [false, true]) {
  for (const firstScreen of ["question", "intro"]) {
    test(`early ${firstScreen} transition guards the next tap and moves focus (reduced motion: ${reducedMotion})`, (t) => {
      const spec = firstScreen === "intro" ? withIntro() : example;
      const action = firstScreen === "intro"
        ? { kind: "advance", screenId: "intro" }
        : { kind: "select", screenId: "role", optionId: "studio" };
      const page = mountedQuiz(t, spec, [action], { reducedMotion });
      assert.equal(page.quiz.snapshot().index, 1);
      assert.equal(page.focused, page.root.querySelector("#quiz-headline"));
      page.clickOption();
      page.tick(180);
      assert.equal(page.quiz.snapshot().index, 1, "the tail of the early tap must not answer another question");
      page.tick(171);
      page.clickOption();
      page.tick(180);
      assert.equal(page.quiz.snapshot().index, 2, "a deliberate later tap must still work");
    });
  }
}

test("plain mount neither steals focus nor delays the first choice", (t) => {
  const page = mountedQuiz(t, example);
  assert.equal(page.focused, null);
  page.clickOption();
  page.tick(180);
  assert.equal(page.quiz.snapshot().screen.id, "behind");
  assert.equal(page.focused, page.root.querySelector("#quiz-headline"));
  page.clickOption();
  page.tick(180);
  assert.equal(page.quiz.snapshot().screen.id, "behind", "ordinary transitions remain guarded");
});

test("an ignored early action does not guard or refocus a restored screen", (t) => {
  const values = new Map();
  const storage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
  createQuiz(example, { storage }).select("studio", "role");
  const page = mountedQuiz(t, example, [{ kind: "select", screenId: "role", optionId: "studio" }], { storage });
  assert.equal(page.quiz.snapshot().screen.id, "behind");
  assert.equal(page.focused, null);
  page.clickOption();
  page.tick(180);
  assert.equal(page.quiz.snapshot().screen.id, "tracking");
});

test("SSR renders an accepted intro safely without browser globals", async () => {
  const html = renderFirstScreen(withIntro());
  assert.ok(html.includes('&lt;Welcome &amp; &quot;hello&quot;&gt;'));
  assert.ok(html.includes('data-quiz-screen="intro"'));
  assert.ok(html.includes('data-quiz-advance>Begin</button>'));
  assert.ok(!html.includes("data-option-id"));
  // Importing the binding on the server does not mount or need document/window.
  const { mountQuiz } = await import("../reference/quiz-page.mjs");
  assert.equal(typeof mountQuiz, "function");
});

test("an early intro continue advances once and reports its event once", () => {
  const events = [];
  const quiz = createQuiz(withIntro(), { onEvent: (event) => events.push(event) });
  const action = { kind: "advance", screenId: "intro" };
  const view = replayEarlyActions(quiz, [action, action]);
  assert.equal(view.screen.id, "role");
  assert.equal(events.length, 1);
  assert.equal(events[0].data.button_role, "quiz_continue");
  assert.equal(quiz.back().screen.id, "intro");
});

test("early actions never apply to a restored later screen", () => {
  const values = new Map();
  const storage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
  const spec = withIntro();
  const first = createQuiz(spec, { storage });
  first.advance("intro");
  first.select("studio", "role");
  const events = [];
  const restored = createQuiz(spec, { storage, onEvent: (event) => events.push(event) });
  assert.equal(replayEarlyActions(restored, [{ kind: "advance", screenId: "intro" }]).screen.id, "behind");
  assert.equal(events.length, 0);
});

test("early single and multi selections preserve accepted answers and privacy", () => {
  const quiz = createQuiz(example);
  assert.equal(replayEarlyActions(quiz, [{ kind: "select", screenId: "role", optionId: "studio" }]).screen.id, "behind");
  const spec = structuredClone(example);
  const question = spec.screens.find((screen) => screen.id === "worries");
  spec.screens = [question, ...spec.screens.filter((screen) => screen !== question)];
  const multi = createQuiz(spec);
  const view = replayEarlyActions(multi, [
    { kind: "toggle", screenId: "worries", optionId: "deadline" },
    { kind: "toggle", screenId: "worries", optionId: "audit" },
  ]);
  assert.deepEqual(view.selected, ["deadline", "audit"]);
  assert.equal(view.screen.id, "worries");
  const sensitive = structuredClone(example);
  sensitive.screens = [sensitive.screens.find((screen) => screen.id === "penalty")];
  assert.ok(renderFirstScreen(sensitive).includes("data-quiz-private"));
});

test("bootstrap captures an intro tap before module loading and stops after mount", async () => {
  let handler;
  const screen = { dataset: { quizScreen: "intro", quizSelect: "interstitial" } };
  const button = { disabled: false, dataset: {}, closest: () => screen };
  const root = {
    addEventListener: (_, callback) => { handler = callback; },
    removeEventListener: (_, callback) => { assert.equal(callback, handler); handler = null; },
    contains: (node) => node === button,
  };
  vm.runInNewContext(await readFile(new URL("../reference/quiz-bootstrap.js", import.meta.url), "utf8"), { document: { querySelectorAll: () => [root] } });
  const event = { target: { closest: () => button }, preventDefault() {} };
  handler(event);
  handler(event);
  assert.equal(root.__quizEarlyActions.length, 1);
  assert.equal(root.__quizEarlyActions[0].kind, "advance");
  root.__quizStopCapture();
  assert.equal(handler, null);
});

test("large multi-select does not enumerate a powerset to prove an early result", () => {
  const spec = structuredClone(example);
  const worries = spec.screens.find((screen) => screen.id === "worries");
  worries.options = Array.from({ length: 60 }, (_, index) => ({ id: `choice-${index}`, label: `Choice ${index}` }));
  spec.results[0].when = { any: [{ screen: "worries", any_of: ["choice-0"] }] };
  const quiz = createQuiz(spec);
  assert.equal(quiz.select("studio", "role").screen.id, "behind");
  quiz.select("few", "behind"); quiz.select("app", "tracking"); quiz.advance("halfway");
  quiz.toggle("choice-0", "worries");
  assert.equal(quiz.advance("worries").atResult, true);
  assert.equal(quiz.result().id, "in-shape");
});
