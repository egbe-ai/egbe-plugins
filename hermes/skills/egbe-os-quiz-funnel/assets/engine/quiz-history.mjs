/**
 * History of a quiz in the browser.
 *
 * Every screen the visitor moves forward to gets its own history entry, so the
 * browser's back returns to the previous screen instead of leaving the quiz.
 * This module keeps the entries consistent. It never touches the DOM: the page
 * passes `window.history` and reports what the visitor and the browser do.
 *
 * An entry records the quiz it belongs to, the index of its screen, and its
 * depth: how many entries of this quiz lie behind it. The address never
 * changes, so an analytics tracker counts no page view.
 */

/**
 * @param {{state: unknown, pushState: Function, replaceState: Function, back: Function}} history
 * @param {string} quizSlug
 */
export function createQuizHistory(history, quizSlug) {
  let depth = 0;

  function entry(index) {
    // What the application's router keeps in the entry stays in it.
    const kept = history.state && typeof history.state === "object" ? history.state : {};
    return { ...kept, quizSlug, quizIndex: index, quizDepth: depth };
  }

  function read(state) {
    if (!state || typeof state !== "object" || state.quizSlug !== quizSlug) return null;
    const { quizIndex, quizDepth } = state;
    if (!Number.isInteger(quizIndex) || quizIndex < 0) return null;
    const recorded = Number.isInteger(quizDepth) && quizDepth >= 0 ? quizDepth : 0;
    // One entry is added per step forward, so no entry lies deeper than its index.
    return { index: quizIndex, depth: Math.min(recorded, quizIndex) };
  }

  return {
    /**
     * Call once when the page shows the quiz, with the index of the screen the
     * engine starts on. After a reload the visitor is still on the entry they
     * were on, and the entries behind it belong to the quiz as before.
     */
    mount(index) {
      const current = read(history.state);
      depth = current && current.index === index ? current.depth : 0;
      history.replaceState(entry(index), "");
    },

    /** Call when the visitor has moved forward to the screen with this index. */
    forward(index) {
      depth += 1;
      history.pushState(entry(index), "");
    },

    /**
     * Call when the visitor presses the back control of the quiz. Returns true
     * when the browser steps back and `follow` will report the screen. Returns
     * false when no entry of the quiz lies behind this one: the page then goes
     * back by itself and calls `replace`.
     */
    back() {
      if (depth === 0) return false;
      history.back();
      return true;
    },

    /** Call after the page went back by itself, with the index it shows now. */
    replace(index) {
      history.replaceState(entry(index), "");
    },

    /**
     * Call with the state of the entry the browser moved to. Returns the index
     * of the screen to show, or null when the entry is not of this quiz.
     */
    follow(state) {
      const target = read(state);
      if (!target) return null;
      depth = target.depth;
      return target.index;
    },

    /** How many entries of this quiz lie behind the current one. */
    get depth() {
      return depth;
    },
  };
}
