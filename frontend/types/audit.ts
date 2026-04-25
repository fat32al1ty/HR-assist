// ResumeAuditOut — mirrors backend schema from Phase 5.0 slice 5.0.1
// Used by all audit components. No optional chaining shortcuts — each field is
// exactly as the backend emits it.

// OnboardingQuestionOut — mirrors backend OnboardingQuestionOut schema (Phase 5.0.2)
export interface OnboardingQuestionOut {
  id: string;
  text: string;
  answer_type: 'choice' | 'number_range' | 'text' | 'boolean';
  choices?: string[];
}

export interface RoleEntry {
  role_family: string;
  seniority: string;
  confidence: number; // 0–1
}

export interface RoleRead {
  primary: RoleEntry;
  alt: RoleEntry[];
}

export interface MarketSalary {
  p25: number;
  p50: number;
  p75: number;
  currency: 'RUB';
  model_version: string;
  user_expectation: number | null;
  gap_to_median_pct: number | null; // negative = below market
  sample_size: number | null;
}

export type QualityIssueSeverity = 'info' | 'warn' | 'error';

export interface QualityIssue {
  rule_id: string;
  severity: QualityIssueSeverity;
  message: string;
}

export interface SkillGap {
  skill: string;
  vacancies_with_skill_pct: number; // 0–100
  vacancies_count_in_segment: number;
  owned: boolean;
}

export interface ResumeAuditOut {
  resume_id: number;
  computed_at: string; // ISO-8601
  prompt_version: string;
  template_mode_active: boolean;
  role_read: RoleRead;
  market_salary: MarketSalary | null;
  skill_gaps: SkillGap[];
  quality_issues: QualityIssue[];
  triggered_question_ids: string[];
}
