export type RequirementCheckStatus = 'ok' | 'partial' | 'missing' | 'unknown';

export type RequirementItem = {
  text: string;
  status: RequirementCheckStatus;
  evidence?: string | null;
  user_overridden?: boolean;
};

export type RequirementsCheck = {
  must_have: RequirementItem[];
  nice_to_have: RequirementItem[];
  experience?: {
    required_years: number;
    candidate_years?: number | null;
    status: RequirementCheckStatus;
  } | null;
};
