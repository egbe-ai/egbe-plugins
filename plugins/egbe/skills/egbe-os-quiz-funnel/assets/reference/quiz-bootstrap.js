/** Load as a small classic script after server-rendered quiz markup, before the module. */
(() => {
  for (const root of document.querySelectorAll("[data-quiz]")) {
    root.__quizEarlyActions = [];
    function capture(event) {
      const button = event.target.closest("[data-option-id], [data-quiz-advance]");
      const screen = button?.closest("[data-quiz-screen]");
      if (!screen || !root.contains(button) || button.disabled) return;
      event.preventDefault();
      const action = { screenId: screen.dataset.quizScreen };
      if (button.dataset.optionId) {
        action.optionId = button.dataset.optionId;
        action.kind = screen.dataset.quizSelect === "multi" ? "toggle" : "select";
        if (action.kind === "select") root.__quizEarlyActions = [];
        button.setAttribute("aria-pressed", action.kind === "select" || button.getAttribute("aria-pressed") !== "true" ? "true" : "false");
        if (action.kind === "select") {
          for (const other of screen.querySelectorAll("[data-option-id]")) {
            if (other !== button) other.setAttribute("aria-pressed", "false");
          }
        }
      } else {
        action.kind = "advance";
        if (root.__quizEarlyActions.some((entry) => entry.kind === "advance")) return;
        button.disabled = true;
      }
      root.__quizEarlyActions.push(action);
    }
    root.addEventListener("click", capture);
    root.__quizStopCapture = () => root.removeEventListener("click", capture);
  }
})();
