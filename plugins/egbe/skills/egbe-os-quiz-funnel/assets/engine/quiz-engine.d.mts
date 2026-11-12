export declare const PUBLIC_CONTRACT: "quiz-funnel-public-v1";

export interface QuizOption {
  id: string;
  label: string;
  phrase?: string;
  escape?: boolean;
}

export interface QuizQuestion {
  id: string;
  type: "question";
  select: "single" | "multi";
  headline: string;
  lead?: string;
  hint?: string;
  button?: string;
  sensitive?: boolean;
  options: QuizOption[];
}

export interface QuizCondition {
  screen: string;
  any_of?: string[];
  none_of?: string[];
}

export type QuizWhen = { all: QuizCondition[] } | { any: QuizCondition[] };

export interface QuizMedia {
  src: string;
  alt: string;
}

export interface QuizInterstitialSpec {
  id: string;
  type: "interstitial";
  kind: "encouragement" | "proof" | "teach";
  headline: string;
  body?: string;
  points?: string[];
  proof_ids?: string[];
  media?: QuizMedia;
  button: string;
  variants?: Array<{
    when: QuizWhen;
    headline?: string;
    body?: string;
    points?: string[];
    proof_ids?: string[];
    media?: QuizMedia;
  }>;
}

export interface QuizProof {
  kind: "count" | "fact" | "logo" | "statistic" | "testimonial";
  text: string;
  author?: string;
  citation?: string;
}

export type QuizShownProof = QuizProof & { id: string };

/** An interstitial screen as the visitor sees it for the answers given so far. */
export interface QuizInterstitial {
  id: string;
  type: "interstitial";
  kind: "encouragement" | "proof" | "teach";
  headline: string;
  body?: string;
  points: string[];
  proof: QuizShownProof[];
  media: QuizMedia | null;
  button: string;
}

export interface QuizLink {
  kind: "link";
  path?: string;
  url?: string;
}

export interface QuizResultSpec {
  id: string;
  fit: "fit" | "partial" | "not_fit";
  when?: QuizWhen;
  headline: string;
  body: string;
  points?: string[];
  proof_ids?: string[];
  media?: QuizMedia;
  cta: { label: string; note?: string; destination?: QuizLink } | null;
}

export type QuizGoalDestination =
  | {
      kind: "booking_url";
      url: string;
      fallback_params?: Record<string, string>;
      result_param?: string;
    }
  | {
      kind: "lead_form";
      action: string;
      fields: string[];
      field_labels: Record<string, string>;
      submit_label: string;
      consent_note?: string;
      error: string;
      success: { headline: string; body: string };
    }
  | { kind: "signup"; path: string }
  | { kind: "checkout"; path: string; plan_key: string; price: string; plan_param?: string };

/**
 * The compiled `quiz.public.json`. Literal fields are typed as `string` so
 * that a JSON import can be passed to `createQuiz` without a cast; the engine
 * checks the contract when it starts.
 */
export interface QuizSpec {
  contract: string;
  spec_sha256: string;
  public_sha256: string;
  quiz_slug: string;
  product_slug: string;
  route: string;
  language: string;
  title: string;
  ui: { back: string; progress: string };
  goal: { type: string; destination: { kind: string; [field: string]: unknown } };
  proof: Record<string, { kind: string; text: string; author?: string; citation?: string }>;
  screens: Array<{ id: string; type: string; [field: string]: unknown }>;
  results: Array<{ id: string; fit: string; [field: string]: unknown }>;
}

export interface QuizEvent {
  name: "button_click" | "cta_click";
  data: Record<string, string | number>;
}

export interface QuizStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface QuizSnapshot {
  index: number;
  total: number;
  position: number;
  progressLabel: string;
  atResult: boolean;
  canGoBack: boolean;
  canAdvance: boolean;
  screen: QuizQuestion | QuizInterstitial | null;
  selected: string[];
}

export interface QuizResult {
  id: string;
  fit: "fit" | "partial" | "not_fit";
  headline: string;
  body: string;
  points: string[];
  proof: QuizShownProof[];
  media: QuizMedia | null;
  hasCta: boolean;
}

export type QuizAttribution = Record<string, string>;

export type QuizDestination =
  | { kind: "booking_url" | "signup" | "checkout" | "link"; href: string }
  | {
      kind: "lead_form";
      action: string;
      fields: string[];
      fieldLabels: Record<string, string>;
      submitLabel: string;
      consentNote: string | null;
      error: string;
      success: { headline: string; body: string };
      payload: {
        quiz_slug: string;
        result_id: string;
        /** Answers to sensitive questions are left out. */
        answers: Record<string, string[]>;
        attribution: QuizAttribution;
      };
    };

export interface QuizCta {
  label: string;
  note: string | null;
  destination: QuizDestination;
  event: QuizEvent;
}

export interface Quiz {
  snapshot(): QuizSnapshot;
  /**
   * Answer the current single-select question. Leads to the next screen, or
   * straight to the result when the answers decide a not_fit result.
   */
  select(optionId: string, expectedScreenId?: string): QuizSnapshot;
  toggle(optionId: string, expectedScreenId?: string): QuizSnapshot;
  /** Like select(): the result follows at once when the answers decide a not_fit result. */
  advance(expectedScreenId?: string): QuizSnapshot;
  /** The previous screen; from a not_fit result decided early, the question that decided it. */
  back(): QuizSnapshot;
  /** A screen already reached; after an early not_fit result, not the skipped screens. */
  goTo(index: number): QuizSnapshot;
  restart(): QuizSnapshot;
  /** The result on screen: after the last screen, or at once for a not_fit result the answers decide. */
  result(): QuizResult | null;
  cta(attribution?: Record<string, unknown>): QuizCta | null;
  /** Every answer, including those to sensitive questions. Keep them on the page. */
  answers(): Record<string, string[]>;
}

export declare function createQuiz(
  spec: QuizSpec,
  options?: { storage?: QuizStorage | null; onEvent?: (event: QuizEvent) => void },
): Quiz;
