// strategy.ts — mirrors backend VacancyStrategyOut schema (Phase 5.2.2)
// and the RecommendationCorrection endpoints.

export interface MatchHighlight {
  /** Index of the resume experience entry that was matched */
  experience_index: number;
  /** Company the experience came from, may be null */
  company: string | null;
  /** One-line quote extracted from the resume or synthesised by the LLM */
  quote: string;
}

export interface GapMitigation {
  /** Vacancy requirement the user lacks */
  requirement: string;
  /** Snippet from the user's profile that was used as a signal, may be null */
  user_signal: string | null;
  /** Mitigation text for the cover letter */
  mitigation_text: string;
}

export interface VacancyStrategyOut {
  resume_id: number;
  vacancy_id: number;
  match_highlights: MatchHighlight[];
  gap_mitigations: GapMitigation[];
  cover_letter_draft: string;
  /** True when the LLM budget is exhausted; template fallback is active */
  template_mode: boolean;
  prompt_version: string;
  /** ISO-8601 timestamp */
  computed_at: string;
}

export type CorrectionType =
  | 'match_highlight_invalid'
  | 'gap_mitigation_invalid';

export interface RecommendationCorrectionCreate {
  resume_id: number;
  vacancy_id: number;
  correction_type: CorrectionType;
  subject_index: number;
  subject_text?: string;
}

export interface RecommendationCorrectionRead {
  id: number;
  resume_id: number;
  vacancy_id: number;
  correction_type: CorrectionType;
  subject_index: number;
  subject_text: string | null;
  created_at: string;
}
