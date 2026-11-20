import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createQuiz } from "./quiz-engine.mjs";
import { createQuizHistory } from "./quiz-history.mjs";

const spec = JSON.parse(
  await readFile(
    new URL("../examples/egbe-docs/product/quizzes/books-checkup/quiz.public.json", import.meta.url),
    "utf8",
  ),
);
const SLUG = spec.quiz_slug;

/** The history of one browser tab: entries, a position, and a listener for moves. */
function browserTab(entries = [{ page: "before the quiz", state: null }]) {
  let position = entries.length - 1;
  let listener = () => {};
  return {
    get state() {
      return entries[position].state;
    },
    pushState(state) {
      entries.splice(position + 1, entries.length, { page: entries[position].page, state });
      position += 1;
    },
    replaceState(state) {
      entries[position] = { ...entries[position], state };
    },
    back() {
      if (position === 0) return;
      position -= 1;
      listener(entries[position].state);
    },
    forward() {
      if (position === entries.length - 1) return;
      position += 1;
      listener(entries[position].state);
    },
    /** The visitor opens another document, such as the page of the quiz. */
    open(page) {
      entries.splice(position + 1, entries.length, { page, state: null });
      position += 1;
    },
    onMove(callback) {
      listener = callback;
    },
    get page() {
      return entries[position].page;
    },
    get entries() {
      return entries.map((entry) => entry.state);
    },
  };
}

function memoryStorage() {
  const items = new Map();
  return {
    getItem: (key) => (items.has(key) ? items.get(key) : null),
    setItem: (key, value) => items.set(key, String(value)),
    removeItem: (key) => items.delete(key),
  };
}

/**
 * The page of the quiz as the reference binding wires it: the engine, the
 * history of the quiz, and the listener for the browser's own moves.
 */
function openQuiz(tab, storage, quizSpec = spec) {
  const quiz = createQuiz(quizSpec, { storage });
  const history = createQuizHistory(tab, quizSpec.quiz_slug);
  tab.onMove((state) => {
    const index = history.follow(state);
    if (index !== null) quiz.goTo(index);
  });
  history.mount(quiz.snapshot().index);
  return {
    quiz,
    history,
    screen: () => quiz.snapshot().screen?.id ?? "result",
    answer(optionId) {
      history.forward(quiz.select(optionId).index);
    },
    pressBack() {
      if (history.back()) return;
      history.replace(quiz.back().index);
    },
  };
}

function quizPage() {
  const tab = browserTab();
  tab.open("quiz");
  return tab;
}

test("intro-first history restores and returns to the introduction", () => {
  const introduced = structuredClone(spec);
  introduced.screens.unshift({ id: "intro", type: "interstitial", kind: "teach", headline: "Welcome", button: "Start" });
  const tab = quizPage();
  const storage = memoryStorage();
  let page = openQuiz(tab, storage, introduced);
  assert.equal(page.screen(), "intro");
  page.history.forward(page.quiz.advance("intro").index);
  page.answer("studio");
  page = openQuiz(tab, storage, introduced);
  assert.equal(page.screen(), "behind");
  page.pressBack();
  assert.equal(page.screen(), "role");
  page.pressBack();
  assert.equal(page.screen(), "intro");
  tab.back();
  assert.equal(tab.page, "before the quiz");
});

test("every step forward adds an entry and the browser's back follows them", () => {
  const tab = quizPage();
  const page = openQuiz(tab, memoryStorage());
  page.answer("studio");
  page.answer("year");

  assert.deepEqual(tab.entries, [
    null,
    { quizSlug: SLUG, quizIndex: 0, quizDepth: 0 },
    { quizSlug: SLUG, quizIndex: 1, quizDepth: 1 },
    { quizSlug: SLUG, quizIndex: 2, quizDepth: 2 },
  ]);

  tab.back();
  assert.equal(page.screen(), "behind");
  assert.equal(page.history.depth, 1);
  tab.forward();
  assert.equal(page.screen(), "tracking");
  assert.equal(page.history.depth, 2);
});

test("the back control of the quiz steps through the same entries", () => {
  const tab = quizPage();
  const page = openQuiz(tab, memoryStorage());
  page.answer("studio");
  page.answer("year");

  page.pressBack();
  assert.equal(page.screen(), "behind");
  page.pressBack();
  assert.equal(page.screen(), "role");
  assert.equal(page.history.depth, 0);

  tab.back();
  assert.equal(tab.page, "before the quiz", "back from the first question leaves the quiz");
});

test("after a reload the back control still steps through the entries", () => {
  const tab = quizPage();
  const storage = memoryStorage();
  const before = openQuiz(tab, storage);
  before.answer("studio");
  before.answer("year");

  // The reload keeps the tab's history and the session storage, not the page.
  const page = openQuiz(tab, storage);
  assert.equal(page.screen(), "tracking");
  assert.equal(page.history.depth, 2);
  assert.deepEqual(tab.state, { quizSlug: SLUG, quizIndex: 2, quizDepth: 2 });

  page.pressBack();
  assert.equal(page.screen(), "behind");
  page.pressBack();
  assert.equal(page.screen(), "role");

  tab.back();
  assert.equal(tab.page, "before the quiz", "back from the first question leaves the quiz");
});

test("a reload in the middle of the entries keeps the ones ahead and behind", () => {
  const tab = quizPage();
  const storage = memoryStorage();
  const before = openQuiz(tab, storage);
  before.answer("studio");
  before.answer("year");
  tab.back();

  const page = openQuiz(tab, storage);
  assert.equal(page.screen(), "behind");
  assert.equal(page.history.depth, 1);
  tab.forward();
  assert.equal(page.screen(), "tracking");
  page.pressBack();
  page.pressBack();
  assert.equal(page.screen(), "role");
  tab.back();
  assert.equal(tab.page, "before the quiz");
});

test("progress restored without entries of the quiz goes back inside the page", () => {
  const storage = memoryStorage();
  const earlier = openQuiz(quizPage(), storage);
  earlier.answer("studio");
  earlier.answer("year");

  // The visitor comes back to the quiz through a link: a new entry, the same tab.
  const tab = quizPage();
  const page = openQuiz(tab, storage);
  assert.equal(page.screen(), "tracking");
  assert.equal(page.history.depth, 0);

  page.pressBack();
  assert.equal(page.screen(), "behind");
  assert.deepEqual(tab.state, { quizSlug: SLUG, quizIndex: 1, quizDepth: 0 });
  page.pressBack();
  assert.equal(page.screen(), "role");
  assert.equal(tab.entries.length, 2, "going back inside the page adds no entry");

  tab.back();
  assert.equal(tab.page, "before the quiz");
});

test("an entry that does not match the screen of the engine is not trusted", () => {
  const tab = quizPage();
  const before = openQuiz(tab, memoryStorage());
  before.answer("studio");
  before.answer("year");

  // The saved progress is gone, for example because the page changed.
  const page = openQuiz(tab, memoryStorage());
  assert.equal(page.screen(), "role");
  assert.equal(page.history.depth, 0);
  assert.deepEqual(tab.state, { quizSlug: SLUG, quizIndex: 0, quizDepth: 0 });

  // Entries of the earlier progress name screens the visitor cannot reach now.
  tab.back();
  assert.equal(page.screen(), "role");
});

test("entries of another quiz and of the application are left alone", () => {
  const tab = browserTab([{ page: "quiz", state: { router: "kept" } }]);
  const history = createQuizHistory(tab, SLUG);
  history.mount(0);
  assert.deepEqual(tab.state, { router: "kept", quizSlug: SLUG, quizIndex: 0, quizDepth: 0 });
  history.forward(1);
  assert.deepEqual(tab.state, { router: "kept", quizSlug: SLUG, quizIndex: 1, quizDepth: 1 });

  assert.equal(history.follow({ quizSlug: "another-quiz", quizIndex: 3, quizDepth: 3 }), null);
  assert.equal(history.follow({ router: "only" }), null);
  assert.equal(history.follow(null), null);
  assert.equal(history.follow("text"), null);
  assert.equal(history.follow({ quizSlug: SLUG, quizIndex: "2", quizDepth: 2 }), null);
  assert.equal(history.follow({ quizSlug: SLUG, quizIndex: -1, quizDepth: 0 }), null);
  assert.equal(history.depth, 1, "an entry that is not followed changes nothing");
});

test("a damaged depth never exceeds what the screen allows", () => {
  const tab = browserTab([
    { page: "quiz", state: { quizSlug: SLUG, quizIndex: 2, quizDepth: 40 } },
  ]);
  const history = createQuizHistory(tab, SLUG);
  history.mount(2);
  assert.equal(history.depth, 2);

  assert.equal(history.follow({ quizSlug: SLUG, quizIndex: 1, quizDepth: "deep" }), 1);
  assert.equal(history.depth, 0);
  assert.equal(history.back(), false);
});
