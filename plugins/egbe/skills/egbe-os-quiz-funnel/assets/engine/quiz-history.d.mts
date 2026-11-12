/** The part of `window.history` that the quiz uses. */
export interface QuizHistoryTarget {
  readonly state: unknown;
  pushState(data: unknown, unused: string, url?: string | URL | null): void;
  replaceState(data: unknown, unused: string, url?: string | URL | null): void;
  back(): void;
}

export interface QuizHistory {
  /** Call once when the page shows the quiz, with the index the engine starts on. */
  mount(index: number): void;
  /** Call when the visitor has moved forward to the screen with this index. */
  forward(index: number): void;
  /**
   * Call when the visitor presses the back control. True: the browser steps
   * back and `follow` reports the screen. False: go back in the page, then
   * call `replace`.
   */
  back(): boolean;
  /** Call after the page went back by itself, with the index it shows now. */
  replace(index: number): void;
  /** The index of the screen of a history entry, or null when it is not of this quiz. */
  follow(state: unknown): number | null;
  /** How many entries of this quiz lie behind the current one. */
  readonly depth: number;
}

export declare function createQuizHistory(
  history: QuizHistoryTarget,
  quizSlug: string,
): QuizHistory;
