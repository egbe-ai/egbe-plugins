/** Server/build-time rendering of the accepted first screen; no browser globals. */
import { createQuiz } from "../engine/quiz-engine.mjs";

const escape = (value) => String(value).replace(/[&<>"']/g, (character) => (
  { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]
));

export function renderFirstScreen(spec) {
  const { screen } = createQuiz(spec).snapshot();
  const text = (tag, value, attributes = "") => value
    ? `<${tag}${attributes}>${escape(value)}</${tag}>` : "";
  let content = text("p", screen.lead, ' class="quiz-lead"')
    + text("h1", screen.headline, ' class="quiz-headline" id="quiz-headline" tabindex="-1"');
  if (screen.type === "question") {
    content += text("p", screen.hint, ' class="quiz-hint"');
    content += `<div class="quiz-options" role="group" aria-labelledby="quiz-headline"${screen.sensitive ? " data-quiz-private" : ""}>`;
    for (const option of screen.options) {
      content += `<button type="button" class="quiz-option" data-option-id="${escape(option.id)}" aria-pressed="false">${escape(option.label)}</button>`;
    }
    content += "</div>";
    if (screen.select === "multi") {
      content += `<button type="button" class="quiz-continue" disabled>${escape(screen.button)}</button>`;
    }
  } else {
    content += text("p", screen.body, ' class="quiz-body"');
    if (screen.media) content += `<img class="quiz-media" src="${escape(screen.media.src)}" alt="${escape(screen.media.alt)}">`;
    if (screen.points.length) content += `<ul class="quiz-points">${screen.points.map((point) => text("li", point)).join("")}</ul>`;
    if (screen.proof.length) content += `<ul class="quiz-proof">${screen.proof.map((proof) => `<li>${text("span", proof.text)}${text("cite", proof.author)}${text("small", proof.citation)}</li>`).join("")}</ul>`;
    content += `<button type="button" class="quiz-continue" data-quiz-advance>${escape(screen.button)}</button>`;
  }
  return `<section class="quiz-screen" data-quiz-screen="${escape(screen.id)}" data-quiz-select="${screen.select ?? "interstitial"}">${content}</section>`;
}
