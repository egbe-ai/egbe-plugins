/**
 * Quiz funnel engine.
 *
 * Holds the state of one compiled quiz (`quiz.public.json`), resolves what each
 * screen and the result say for the given answers, builds the call-to-action
 * destination, and describes the canonical analytics events. It never touches
 * the DOM, the network, or an analytics tracker: the page supplies `storage`
 * and `onEvent` and renders `snapshot()`.
 */

export const PUBLIC_CONTRACT = "quiz-funnel-public-v1";

const UTM_FIELDS = [
  ["utm_source", "first_utm_source"],
  ["utm_medium", "first_utm_medium"],
  ["utm_campaign", "first_utm_campaign"],
  ["utm_content", "first_utm_content"],
  ["utm_term", "first_utm_term"],
];

const ATTRIBUTION_FIELDS = [
  "visitor_id",
  "visit_id",
  "first_utm_source",
  "first_utm_medium",
  "first_utm_campaign",
  "first_utm_content",
  "first_utm_term",
  "first_gclid",
  "first_fbclid",
  "first_msclkid",
  "first_ttclid",
  "first_landing_path",
  "first_referrer",
  "first_seen_at",
];

const CTA_ROLES = {
  call: "call_primary",
  signup: "signup_primary",
  payment: "checkout_primary",
};

const TOKEN = /\{\{\s*answer:([a-z][a-z0-9_-]{0,39})\s*\}\}/g;

/**
 * How many combinations of the remaining answers the engine tries to decide a
 * not_fit result early. Beyond it the visitor answers every question first.
 */
const EARLY_LIMIT = 4096;

function assertSpec(spec) {
  if (!spec || spec.contract !== PUBLIC_CONTRACT) {
    throw new Error(`quiz specification must use the contract ${PUBLIC_CONTRACT}`);
  }
  if (!Array.isArray(spec.screens) || spec.screens.length === 0) {
    throw new Error("quiz specification has no screens");
  }
  if (!Array.isArray(spec.results) || spec.results.length === 0) {
    throw new Error("quiz specification has no results");
  }
}

function cleanAttribution(attribution) {
  const clean = {};
  for (const field of ATTRIBUTION_FIELDS) {
    const value = attribution?.[field];
    if (typeof value === "string" && value.trim()) clean[field] = value.trim();
  }
  return clean;
}

function withParam(path, name, value) {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}${encodeURIComponent(name)}=${encodeURIComponent(value)}`;
}

function copy(value) {
  return JSON.parse(JSON.stringify(value));
}

function withoutQuery(path) {
  return path.split("?", 1)[0];
}

function originAndPath(href) {
  const url = new URL(href);
  return `${url.origin}${url.pathname}`;
}

/**
 * @param {object} spec Compiled public specification.
 * @param {{storage?: Storage | null, onEvent?: (event: {name: string, data: object}) => void}} [options]
 */
export function createQuiz(spec, options = {}) {
  assertSpec(spec);

  const screens = spec.screens;
  const total = screens.length;
  const storage = options.storage ?? null;
  const emit = typeof options.onEvent === "function" ? options.onEvent : () => {};
  const storageKey = `quiz-funnel:${spec.quiz_slug}`;
  const questions = new Map(
    screens.filter((screen) => screen.type === "question").map((screen) => [screen.id, screen]),
  );
  // Only the questions a result condition names can change which result is shown.
  const named = new Set(
    spec.results.flatMap((result) =>
      result.when ? (result.when.all ?? result.when.any).map((condition) => condition.screen) : [],
    ),
  );

  let state = restore() ?? { index: 0, answers: {} };

  /** The first screen the visitor cannot pass yet: an unanswered question, or the result. */
  function furthest(answers) {
    const open = screens.findIndex(
      (screen) => screen.type === "question" && !(answers[screen.id]?.length > 0),
    );
    return open === -1 ? total : open;
  }

  /** Every answer a question can receive: one option, or a set of a multi-select question. */
  function choicesOf(question, budget) {
    if (question.select === "single") {
      if (question.options.length > budget) return null;
      return question.options.map((option) => [option.id]);
    }
    const escapes = question.options.filter((option) => option.escape).map((option) => option.id);
    const others = question.options.filter((option) => !option.escape).map((option) => option.id);
    // Do not allocate a powerset just to discover that early-result analysis
    // exceeds its budget. Large lists remain valid and complete normally.
    if (2 ** others.length - 1 + escapes.length > budget) return null;
    const sets = escapes.map((id) => [id]);
    for (let mask = 1; mask < 2 ** others.length; mask += 1) {
      sets.push(others.filter((_, bit) => Math.floor(mask / (2 ** bit)) % 2));
    }
    return sets;
  }

  /** The result a finished quiz shows for these answers: the first that matches. */
  function firstMatch(answers) {
    return spec.results.find((candidate) => matchesIn(candidate.when, answers)) ?? null;
  }

  /** The questions a headline or body of a result quotes. */
  function quotedInSentences(result) {
    return [result.headline, result.body].flatMap((text) =>
      [...String(text ?? "").matchAll(TOKEN)].map((match) => match[1]),
    );
  }

  /**
   * The not_fit result that the answers up to the screen `upTo` decide: the
   * first match for every answer the later questions could still receive. Null
   * when a later answer could change the result, when the result would quote a
   * question not answered yet, or when too many answers remain to be sure.
   */
  function decidedBy(known, upTo) {
    const open = screens.filter(
      (screen, index) => index > upTo && screen.type === "question" && named.has(screen.id),
    );
    const choices = [];
    let combinations = 1;
    for (const question of open) {
      const next = choicesOf(question, Math.floor(EARLY_LIMIT / combinations));
      if (!next) return null;
      choices.push(next);
      combinations *= next.length;
    }
    const answers = { ...known };
    let decided;
    const every = (depth) => {
      if (depth === open.length) {
        const found = firstMatch(answers);
        if (!found || found.fit !== "not_fit") return false;
        decided ??= found;
        return decided === found;
      }
      return choices[depth].every((choice) => {
        answers[open[depth].id] = choice;
        return every(depth + 1);
      });
    };
    if (!every(0)) return null;
    return quotedInSentences(decided).every((id) => known[id]?.length > 0) ? decided : null;
  }

  /**
   * The earliest question after which the answers decide a not_fit result: the
   * result and the index of that question. Answers to later questions are not
   * read, so an answer left from an earlier path changes nothing. Null when no
   * question up to the first unanswered one decides such a result.
   */
  function decision(answers) {
    const known = {};
    for (let index = 0; index < total; index += 1) {
      const screen = screens[index];
      if (screen.type !== "question") continue;
      if (!(answers[screen.id]?.length > 0)) return null;
      known[screen.id] = answers[screen.id];
      const result = decidedBy(known, index);
      if (result) return { result, index, answers: { ...known } };
    }
    return null;
  }

  /**
   * Whether a screen, or the result at `total`, can be shown for these answers.
   * Once the answers decide a not_fit result, the screens after the deciding
   * question are skipped.
   */
  function reachable(index, answers) {
    if (!Number.isInteger(index) || index < 0 || index > total) return false;
    const decided = decision(answers);
    if (decided) return index <= decided.index || index === total;
    return index <= furthest(answers);
  }

  function restore() {
    if (!storage) return null;
    let saved;
    try {
      saved = JSON.parse(storage.getItem(storageKey) ?? "null");
    } catch {
      return null;
    }
    if (!saved || saved.version !== spec.public_sha256) return null;
    const { index, answers } = saved;
    if (!answers || typeof answers !== "object" || Array.isArray(answers)) return null;
    for (const [screenId, chosen] of Object.entries(answers)) {
      const question = questions.get(screenId);
      if (!question || !Array.isArray(chosen)) return null;
      const known = new Set(question.options.map((option) => option.id));
      if (chosen.some((optionId) => !known.has(optionId))) return null;
      if (new Set(chosen).size !== chosen.length) return null;
      if (question.select === "single" && chosen.length > 1) return null;
    }
    if (!Number.isInteger(index) || index < 0 || index > total) return null;
    // A saved screen after the question that decides a not_fit result shows that result.
    const decided = decision(answers);
    const shown = decided && index > decided.index ? total : index;
    if (!reachable(shown, answers)) return null;
    return { index: shown, answers };
  }

  function save() {
    if (!storage) return;
    try {
      storage.setItem(storageKey, JSON.stringify({ version: spec.public_sha256, ...state }));
    } catch {
      // Storage can be full or blocked; the quiz still works for this page view.
    }
  }

  function current() {
    return state.index < total ? screens[state.index] : null;
  }

  /** False when the page asks to act on a screen the visitor has already left. */
  function isCurrent(expectedScreenId) {
    return expectedScreenId === undefined || current()?.id === expectedScreenId;
  }

  function payload(surface, fields) {
    return { product_slug: spec.product_slug, path: spec.route, surface, ...fields };
  }

  function requireQuestion(select) {
    const screen = current();
    if (!screen || screen.type !== "question" || screen.select !== select) {
      throw new Error(`the current screen is not a ${select}-select question`);
    }
    return screen;
  }

  function requireOption(screen, optionId) {
    const option = screen.options.find((candidate) => candidate.id === optionId);
    if (!option) throw new Error(`screen ${screen.id} has no option ${optionId}`);
    return option;
  }

  /** The options chosen for a question, in the order the screen lists them. */
  function chosenOptions(screenId, answers = state.answers) {
    const question = questions.get(screenId);
    const chosen = answers[screenId] ?? [];
    return question ? question.options.filter((option) => chosen.includes(option.id)) : [];
  }

  function matchesIn(when, answers) {
    if (!when) return true;
    const test = (condition) => {
      const chosen = answers[condition.screen] ?? [];
      if (condition.any_of) return condition.any_of.some((id) => chosen.includes(id));
      return !condition.none_of.some((id) => chosen.includes(id));
    };
    return when.all ? when.all.every(test) : when.any.some(test);
  }

  function matches(when) {
    return matchesIn(when, state.answers);
  }

  /** A headline or body: each token becomes the chosen option, worded for a sentence. */
  function fillSentence(text, answers = state.answers) {
    return text.replace(TOKEN, (_, screenId) => {
      const [option] = chosenOptions(screenId, answers);
      return option ? (option.phrase ?? option.label) : "";
    });
  }

  /**
   * A point: each token becomes the chosen options, separated by commas. The
   * point is dropped when a question it quotes was declined or not answered.
   */
  function fillPoint(text, answers = state.answers) {
    let complete = true;
    const filled = text.replace(TOKEN, (_, screenId) => {
      const chosen = chosenOptions(screenId, answers);
      if (chosen.length === 0 || chosen.some((option) => option.escape)) {
        complete = false;
        return "";
      }
      return chosen.map((option) => option.phrase ?? option.label).join(", ");
    });
    return complete ? filled : null;
  }

  function fillPoints(points, answers = state.answers) {
    return (points ?? []).map((point) => fillPoint(point, answers)).filter((point) => point !== null);
  }

  function proofOf(ids) {
    return (ids ?? []).map((id) => ({ id, ...spec.proof[id] }));
  }

  /** An interstitial screen as the visitor sees it for the answers given so far. */
  function resolveInterstitial(screen) {
    const variant = (screen.variants ?? []).find((candidate) => matches(candidate.when)) ?? {};
    const shown = { ...screen, ...variant };
    const resolved = {
      id: screen.id,
      type: screen.type,
      kind: screen.kind,
      headline: fillSentence(shown.headline),
      points: fillPoints(shown.points),
      proof: proofOf(shown.proof_ids),
      media: shown.media ?? null,
      button: screen.button,
    };
    if (shown.body) resolved.body = fillSentence(shown.body);
    return resolved;
  }

  function step() {
    // A not_fit result appears as soon as the answers decide it: the questions
    // after the deciding one could not change it.
    const decided = decision(state.answers);
    const next = decided && decided.index <= state.index ? total : state.index + 1;
    state = { ...state, index: next };
    save();
    return snapshot();
  }

  function snapshot() {
    const screen = current();
    const selected = screen?.type === "question" ? [...(state.answers[screen.id] ?? [])] : [];
    const position = Math.min(state.index + 1, total);
    let canAdvance = false;
    if (screen?.type === "interstitial") canAdvance = true;
    if (screen?.type === "question" && screen.select === "multi") canAdvance = selected.length > 0;
    return {
      index: state.index,
      total,
      position,
      progressLabel: spec.ui.progress
        .replace("{current}", String(position))
        .replace("{total}", String(total)),
      atResult: screen === null,
      canGoBack: state.index > 0,
      canAdvance,
      screen: screen?.type === "interstitial" ? resolveInterstitial(screen) : screen,
      selected,
    };
  }

  /**
   * Answer the current single-select question and move to the next screen.
   * Pass the id of the screen the visitor tapped on as `expectedScreenId`: a
   * tap that arrives after the screen has changed is ignored.
   */
  function select(optionId, expectedScreenId) {
    if (!isCurrent(expectedScreenId)) return snapshot();
    const screen = requireQuestion("single");
    requireOption(screen, optionId);
    state = { ...state, answers: { ...state.answers, [screen.id]: [optionId] } };
    emit({
      name: "button_click",
      data: payload("quiz", {
        // The chosen option of a sensitive question stays out of analytics.
        button_id: `${screen.id}.${screen.sensitive ? "answered" : optionId}`,
        button_role: "quiz_answer",
        position: state.index + 1,
      }),
    });
    return step();
  }

  /** Switch one option of the current multi-select question on or off. */
  function toggle(optionId, expectedScreenId) {
    if (!isCurrent(expectedScreenId)) return snapshot();
    const screen = requireQuestion("multi");
    const option = requireOption(screen, optionId);
    const chosen = state.answers[screen.id] ?? [];
    let next;
    if (chosen.includes(optionId)) {
      next = chosen.filter((id) => id !== optionId);
    } else if (option.escape) {
      next = [optionId];
    } else {
      const escapes = new Set(
        screen.options.filter((candidate) => candidate.escape).map((candidate) => candidate.id),
      );
      next = [...chosen.filter((id) => !escapes.has(id)), optionId];
    }
    state = { ...state, answers: { ...state.answers, [screen.id]: next } };
    save();
    return snapshot();
  }

  /** Leave an interstitial screen or confirm a multi-select question. */
  function advance(expectedScreenId) {
    if (!isCurrent(expectedScreenId)) return snapshot();
    const screen = current();
    if (!screen) throw new Error("the quiz is already at its result");
    if (screen.type === "interstitial") {
      emit({
        name: "button_click",
        data: payload("quiz", {
          button_id: `${screen.id}.continue`,
          button_role: "quiz_continue",
          position: state.index + 1,
        }),
      });
      return step();
    }
    if (screen.select !== "multi") {
      throw new Error("a single-select question advances through select()");
    }
    const chosen = chosenOptions(screen.id).map((option) => option.id);
    if (chosen.length === 0) throw new Error(`screen ${screen.id} needs at least one option`);
    emit({
      name: "button_click",
      data: payload("quiz", {
        button_id: `${screen.id}.continue`,
        button_role: "quiz_answer",
        ...(screen.sensitive ? {} : { state: chosen.join("+") }),
        position: state.index + 1,
      }),
    });
    return step();
  }

  /**
   * Return to the previous screen. Answers are kept. From a not_fit result
   * that the answers decided early, return to the question that decided it.
   */
  function back() {
    if (state.index === total) {
      const decided = decision(state.answers);
      if (decided) return goTo(decided.index);
    }
    return goTo(state.index - 1);
  }

  /**
   * Show a screen the visitor has already reached, for the browser's own back
   * and forward. An index that is out of reach changes nothing.
   */
  function goTo(index) {
    if (reachable(index, state.answers)) {
      state = { ...state, index };
      save();
    }
    return snapshot();
  }

  function restart() {
    state = { index: 0, answers: {} };
    try {
      storage?.removeItem(storageKey);
    } catch {
      // Nothing to clear when storage is blocked.
    }
    return snapshot();
  }

  /**
   * The result on screen and the answers it may quote: a not_fit result the
   * answers decided quotes only the answers up to the deciding question.
   */
  function shownResult() {
    if (current() !== null) return null;
    const decided = decision(state.answers);
    if (decided) return { result: decided.result, answers: decided.answers };
    const result = firstMatch(state.answers);
    return result ? { result, answers: state.answers } : null;
  }

  function selectedResult() {
    return shownResult()?.result ?? null;
  }

  /**
   * The result for the given answers, or null while it is not on screen: before
   * the last screen is passed, unless the answers decided a not_fit result.
   */
  function result() {
    const shown = shownResult();
    if (!shown) return null;
    const { result: selected, answers } = shown;
    return {
      id: selected.id,
      fit: selected.fit,
      headline: fillSentence(selected.headline, answers),
      body: fillSentence(selected.body, answers),
      points: fillPoints(selected.points, answers),
      proof: proofOf(selected.proof_ids),
      media: selected.media ?? null,
      hasCta: selected.cta !== null,
    };
  }

  /** The answers without those to sensitive questions, which stay on the page. */
  function shareableAnswers() {
    const shareable = {};
    for (const [screenId, chosen] of Object.entries(state.answers)) {
      if (!questions.get(screenId)?.sensitive) shareable[screenId] = [...chosen];
    }
    return shareable;
  }

  function bookingHref(destination, resultId, attribution) {
    const url = new URL(destination.url);
    const params = url.searchParams;
    if (destination.result_param && !params.has(destination.result_param)) {
      params.set(destination.result_param, `${spec.quiz_slug}.${resultId}`);
    }
    let arrivedWithCampaign = false;
    for (const [param, field] of UTM_FIELDS) {
      if (!attribution[field]) continue;
      arrivedWithCampaign = true;
      if (!params.has(param)) params.set(param, attribution[field]);
    }
    // Fallback values describe a visitor who arrived without any campaign
    // parameters. They never complete a real campaign with invented values.
    if (!arrivedWithCampaign) {
      for (const [param, value] of Object.entries(destination.fallback_params ?? {})) {
        if (!params.has(param)) params.set(param, value);
      }
    }
    return url.toString();
  }

  function resolveDestination(selected, attribution) {
    const override = selected.cta.destination;
    if (override) {
      const href = override.path ?? override.url;
      return {
        kind: "link",
        href,
        tracked: override.path ? withoutQuery(href) : originAndPath(href),
      };
    }
    const destination = spec.goal.destination;
    switch (destination.kind) {
      case "booking_url": {
        const href = bookingHref(destination, selected.id, attribution);
        return { kind: "booking_url", href, tracked: originAndPath(href) };
      }
      case "lead_form":
        return {
          kind: "lead_form",
          action: destination.action,
          fields: [...destination.fields],
          fieldLabels: { ...destination.field_labels },
          submitLabel: destination.submit_label,
          consentNote: destination.consent_note ?? null,
          error: destination.error,
          success: { ...destination.success },
          payload: {
            quiz_slug: spec.quiz_slug,
            result_id: selected.id,
            answers: shareableAnswers(),
            attribution,
          },
          tracked: withoutQuery(destination.action),
        };
      case "signup":
        return { kind: "signup", href: destination.path, tracked: withoutQuery(destination.path) };
      case "checkout": {
        const href = withParam(
          destination.path,
          destination.plan_param ?? "plan",
          destination.plan_key,
        );
        return { kind: "checkout", href, tracked: withoutQuery(destination.path) };
      }
      default:
        throw new Error(`unknown destination kind ${destination.kind}`);
    }
  }

  /**
   * The call to action of the current result: its label, the note under it,
   * where it leads, and the canonical `cta_click` descriptor. Returns null
   * when the result has no call to action. `attribution` is
   * `window.__egbeAttribution.read()`.
   */
  function cta(attribution = {}) {
    const selected = selectedResult();
    if (!selected || selected.cta === null) return null;
    const { tracked, ...destination } = resolveDestination(selected, cleanAttribution(attribution));
    return {
      label: selected.cta.label,
      note: selected.cta.note ?? null,
      destination,
      event: {
        name: "cta_click",
        data: payload("quiz_result", {
          cta_id: selected.id,
          cta_role: selected.cta.destination ? "alternative" : CTA_ROLES[spec.goal.type],
          label: selected.cta.label,
          destination: tracked,
        }),
      },
    };
  }

  return {
    snapshot,
    select,
    toggle,
    advance,
    back,
    goTo,
    restart,
    result,
    cta,
    answers: () => copy(state.answers),
  };
}
