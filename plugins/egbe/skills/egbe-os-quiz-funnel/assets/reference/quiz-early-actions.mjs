/** Replay only actions from the screen the runtime actually restored. */
export function replayEarlyActions(quiz, actions) {
  for (const action of actions) {
    const view = quiz.snapshot();
    if (view.atResult || action.screenId !== view.screen.id) continue;
    if (action.kind === "advance" && view.screen.type === "interstitial") quiz.advance(action.screenId);
    else if (action.kind === "select" && view.screen.select === "single") quiz.select(action.optionId, action.screenId);
    else if (action.kind === "toggle" && view.screen.select === "multi") quiz.toggle(action.optionId, action.screenId);
  }
  return quiz.snapshot();
}
