'use client';

import { FormEvent, Fragment, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import {
  excludeFeedbackVacancies,
  normalizeVacancyId,
  removeVacancyFromList,
  removeVacancyMatchEntry
} from '../lib/vacancyMatching';
import {
  formatRecommendationHeadline,
  formatRecommendationMetrics
} from '../lib/recommendationStats';
import { createDwellTracker, trackClick } from '../lib/telemetry';
import { API_BASE_URL, RESUME_LIMIT, apiFetch } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useSession } from '@/lib/session';
import { type Resume, resumeDisplayName } from '@/types/resume';
const MIN_PROGRESS_VISIBLE_MS = 1400;
const RECOMMEND_TIMEOUT_MS = 540000;
const LAST_JOB_ID_STORAGE_KEY = 'last_recommendation_job_id';

const RESUME_LABEL_MAX = 32;
type AuthFormMode = 'login' | 'register' | 'reset';

type WorkFormat = 'remote' | 'hybrid' | 'office' | 'any';
type RelocationMode = 'home_only' | 'any_city';
type Seniority = 'junior' | 'middle' | 'senior' | 'lead';

type UserPrefs = {
  preferred_work_format: WorkFormat;
  relocation_mode: RelocationMode;
  home_city: string | null;
  preferred_titles: string[];
  expected_salary_min: number | null;
  expected_salary_max: number | null;
  expected_salary_currency: string;
};

type UserRead = UserPrefs & {
  id: number;
  email: string;
  full_name: string | null;
  is_active: boolean;
  is_admin: boolean;
  email_verified: boolean;
  created_at: string;
};

type ProfileDraft = {
  target_role: string;
  specialization: string;
  seniority: Seniority | '';
  total_experience_years: string;
  top_skills: string[];
  preferred_work_format: WorkFormat;
  relocation_mode: RelocationMode;
  home_city: string;
  preferred_titles: string[];
  expected_salary_min: string;
  expected_salary_max: string;
};

type VacancyMatch = {
  vacancy_id: number;
  title: string;
  source_url: string;
  company: string | null;
  location: string | null;
  similarity_score: number;
  salary_min?: number | null;
  salary_max?: number | null;
  salary_currency?: string | null;
  profile: Record<string, unknown> | null;
  tier?: 'strong' | 'maybe' | null;
  match_run_id?: string | null;
};

type CuratedDirection = 'added' | 'rejected';

type CuratedSkillRead = {
  id: number;
  resume_id: number;
  skill_text: string;
  direction: CuratedDirection;
  source_vacancy_id: number | null;
  created_at: string;
};

type CuratedSkillResponse = {
  skill: CuratedSkillRead;
  warn_sanity_check: boolean;
  recent_added_count: number;
};

type VacancyRecommendResponse = {
  query: string;
  indexed: number;
  fetched: number;
  prefiltered: number;
  analyzed: number;
  filtered: number;
  failed: number;
  already_indexed_skipped: number;
  sources: string[];
  openai_usage: {
    prompt_tokens: number;
    completion_tokens: number;
    embedding_tokens: number;
    total_tokens: number;
    api_calls: number;
    estimated_cost_usd: number;
    budget_usd: number;
    budget_exceeded: boolean;
    budget_enforced: boolean;
  };
  matches: VacancyMatch[];
};

type RecommendationJobStatusResponse = {
  job_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  stage: string;
  progress: number;
  query: string | null;
  metrics: {
    indexed?: number;
    fetched?: number;
    prefiltered?: number;
    analyzed?: number;
    filtered?: number;
    failed?: number;
    already_indexed_skipped?: number;
    sources?: string[];
  };
  matches: VacancyMatch[];
  openai_usage: VacancyRecommendResponse['openai_usage'] | null;
  error_message: string | null;
  active: boolean;
  cancel_requested?: boolean;
};

type DashboardStatsResponse = {
  generated_at: string;
  funnel: {
    resume_id: number | null;
    analyzed_count: number;
    matched_count: number;
    selected_count: number;
    last_search_at: string | null;
    next_warmup_eta: string | null;
  };
};

type WarmupStatusResponse = {
  enabled: boolean;
  running: boolean;
  last_finished_at: string | null;
  interval_seconds: number;
};

const statusLabels: Record<string, string> = {
  completed: 'готово',
  failed: 'ошибка',
  processing: 'в обработке',
  uploaded: 'загружено'
};

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function asText(value: unknown, fallback: string): string {
  return typeof value === 'string' && value.trim() ? value : fallback;
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function missingRequirementsFromMatch(match: VacancyMatch): string[] {
  if (!match.profile || typeof match.profile !== 'object') {
    return [];
  }
  return asStringArray(match.profile.missing_requirements).slice(0, 8);
}

function matchedSkillsFromMatch(match: VacancyMatch): string[] {
  if (!match.profile || typeof match.profile !== 'object') {
    return [];
  }
  return asStringArray(match.profile.matched_skills).slice(0, 10);
}

function matchedRequirementsFromMatch(match: VacancyMatch): string[] {
  if (!match.profile || typeof match.profile !== 'object') {
    return [];
  }
  return asStringArray(match.profile.matched_requirements).slice(0, 10);
}

function reasonFromMatch(match: VacancyMatch): string | null {
  if (!match.profile || typeof match.profile !== 'object') {
    return null;
  }
  const raw = match.profile.reason_ru;
  return typeof raw === 'string' && raw.trim().length > 0 ? raw.trim() : null;
}

function scoreToPercent(score: number): string {
  return `${Math.round(score * 100)}%`;
}

function formatSalaryAmount(amount: number, currency: string): string {
  const symbol = currency === 'RUB' ? ' ₽' : ` ${currency}`;
  const formatted = new Intl.NumberFormat('ru-RU').format(amount);
  return `${formatted}${symbol}`;
}

function renderSalaryBadge(match: VacancyMatch): {
  text: string;
  estimated: boolean;
  fit: string | null;
} | null {
  const currency = match.salary_currency || 'RUB';
  const min = match.salary_min ?? null;
  const max = match.salary_max ?? null;
  const profile = match.profile && typeof match.profile === 'object' ? match.profile : {};
  const source = typeof profile.salary_source === 'string' ? (profile.salary_source as string) : null;
  const fit = typeof profile.salary_fit === 'string' ? (profile.salary_fit as string) : null;
  if (min == null && max == null) {
    return null;
  }
  const estimated = source === 'predicted';
  let text: string;
  if (min != null && max != null && min !== max) {
    text = `${new Intl.NumberFormat('ru-RU').format(min)} – ${formatSalaryAmount(max, currency)}`;
  } else {
    text = formatSalaryAmount(min ?? max ?? 0, currency);
  }
  if (estimated) {
    text = `${text} (оценка)`;
  }
  return { text, estimated, fit };
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function stageLabel(stage: string): string {
  switch (stage) {
    case 'queued':
      return 'В очереди...';
    case 'collecting':
      return 'Ищем и отбираем вакансии...';
    case 'matching':
      return 'Сравниваем с резюме...';
    case 'finalizing':
      return 'Готовим подборку...';
    case 'done':
      return 'Готово';
    case 'failed':
      return 'Ошибка';
    default:
      return 'Выполняется...';
  }
}

function formatCountdown(totalMs: number): string {
  const clamped = Math.max(0, Math.floor(totalMs / 1000));
  const minutes = Math.floor(clamped / 60);
  const seconds = clamped % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function formatRelativeTimeRu(isoString: string | null): string {
  if (!isoString) return '—';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return '—';
  const diffMs = Date.now() - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return 'только что';
  const diffMin = Math.floor(diffSec / 60);
  if (diffMin < 60) return `${diffMin} мин назад`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) {
    const h = diffHour;
    const suffix = h === 1 ? 'час' : h < 5 ? 'часа' : 'часов';
    return `${h} ${suffix} назад`;
  }
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay === 1) return 'вчера';
  if (diffDay < 7) {
    const suffix = diffDay < 5 ? 'дня' : 'дней';
    return `${diffDay} ${suffix} назад`;
  }
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' });
}

const WORK_FORMAT_OPTIONS: { value: WorkFormat; label: string }[] = [
  { value: 'any', label: 'Любой' },
  { value: 'remote', label: 'Удалёнка' },
  { value: 'hybrid', label: 'Гибрид' },
  { value: 'office', label: 'Офис' }
];

const SENIORITY_OPTIONS: { value: Seniority; label: string }[] = [
  { value: 'junior', label: 'Junior' },
  { value: 'middle', label: 'Middle' },
  { value: 'senior', label: 'Senior' },
  { value: 'lead', label: 'Lead' }
];

function isSeniority(value: unknown): value is Seniority {
  return value === 'junior' || value === 'middle' || value === 'senior' || value === 'lead';
}

function buildProfileDraft(resume: Resume, prefs: UserPrefs): ProfileDraft {
  const analysis = resume.analysis || {};
  const years = typeof analysis.total_experience_years === 'number' ? String(analysis.total_experience_years) : '';
  const hardSkills = asStringArray(analysis.hard_skills).slice(0, 3);
  const analysisHomeCity = typeof analysis.home_city === 'string' ? analysis.home_city : '';
  const analysisSeniority = analysis.seniority;
  return {
    target_role: asText(analysis.target_role, ''),
    specialization: asText(analysis.specialization, ''),
    seniority: isSeniority(analysisSeniority) ? analysisSeniority : '',
    total_experience_years: years,
    top_skills: hardSkills,
    preferred_work_format: prefs.preferred_work_format,
    relocation_mode: prefs.relocation_mode,
    home_city: prefs.home_city ?? analysisHomeCity ?? '',
    preferred_titles: prefs.preferred_titles,
    expected_salary_min: prefs.expected_salary_min ? String(prefs.expected_salary_min) : '',
    expected_salary_max: prefs.expected_salary_max ? String(prefs.expected_salary_max) : ''
  };
}

function readStoredJobId(): string | null {
  try {
    const value = window.localStorage.getItem(LAST_JOB_ID_STORAGE_KEY);
    return value && value.trim() ? value : null;
  } catch {
    return null;
  }
}

export default function DashboardPage() {
  const {
    token,
    user,
    setSession,
    clearSession: clearSessionCtx,
    setResumes: setSessionResumes,
    setActivateResumeProfile,
  } = useSession();
  const [authFormMode, setAuthFormMode] = useState<AuthFormMode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [betaKey, setBetaKey] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [resumes, setResumesLocal] = useState<Resume[]>([]);
  const [matches, setMatches] = useState<VacancyMatch[]>([]);
  const [selectedVacancies, setSelectedVacancies] = useState<VacancyMatch[]>([]);
  const [dislikedVacancies, setDislikedVacancies] = useState<VacancyMatch[]>([]);
  const [expandedResumeIds, setExpandedResumeIds] = useState<Record<number, boolean>>({});
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null);
  const [message, setMessage] = useState('');
  const [matchingMessage, setMatchingMessage] = useState('');
  const [openaiUsageMessage, setOpenaiUsageMessage] = useState('');
  const [lastMatchingQuery, setLastMatchingQuery] = useState('');
  const [lastSources, setLastSources] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [matchingBusy, setMatchingBusy] = useState(false);
  const [matchingProgress, setMatchingProgress] = useState(0);
  const [matchingStage, setMatchingStage] = useState('');
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [cancelRequested, setCancelRequested] = useState(false);
  const [hiddenMatchIds, setHiddenMatchIds] = useState<number[]>([]);
  const [dashboardStats, setDashboardStats] = useState<DashboardStatsResponse | null>(null);
  const [warmupStatus, setWarmupStatus] = useState<WarmupStatusResponse | null>(null);
  const [nowTick, setNowTick] = useState(() => Date.now());
  const [userPrefs, setUserPrefs] = useState<UserPrefs | null>(null);
  const [profileDraft, setProfileDraft] = useState<ProfileDraft | null>(null);
  const [profileConfirmed, setProfileConfirmed] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState('');
  const [applyingVacancyIds, setApplyingVacancyIds] = useState<Record<number, boolean>>({});
  const [curatedSkills, setCuratedSkills] = useState<CuratedSkillRead[]>([]);
  const [curatingSkillKey, setCuratingSkillKey] = useState<string | null>(null);
  const isAdmin = Boolean(user?.is_admin);

  /** Syncs resumes into both local state and the Session context. */
  function setResumes(next: Resume[] | ((prev: Resume[]) => Resume[])) {
    setResumesLocal((prev) => {
      const resolved = typeof next === 'function' ? next(prev) : next;
      setSessionResumes(resolved);
      return resolved;
    });
  }

  useEffect(() => {
    const storedJobId = readStoredJobId();
    if (storedJobId) {
      setCurrentJobId(storedJobId);
    }
  }, []);

  useEffect(() => {
    if (!token) {
      return;
    }
    void loadResumes(token);
    void loadSelectedVacancies();
    void loadDislikedVacancies();
    void loadUserPrefs();
  }, [token]);

  useEffect(() => {
    const selectedResume = resumes.find((resume) => resume.id === selectedResumeId) || null;
    if (!selectedResume || !userPrefs) {
      setProfileDraft(null);
      return;
    }
    setProfileDraft(buildProfileDraft(selectedResume, userPrefs));
    setProfileMessage('');
  }, [selectedResumeId, resumes, userPrefs]);

  useEffect(() => {
    if (!token) {
      return;
    }
    void restoreRecommendationState();
  }, [token]);

  useEffect(() => {
    setMatches((current) => {
      const filtered = excludeFeedbackVacancies(current, dislikedVacancies, selectedVacancies, hiddenMatchIds);
      if (filtered.length === current.length) {
        return current;
      }
      return filtered;
    });
  }, [dislikedVacancies, selectedVacancies, hiddenMatchIds]);

  useEffect(() => {
    if (!token) {
      return;
    }
    void loadDashboardStats(selectedResumeId);
  }, [token, selectedResumeId]);

  useEffect(() => {
    if (!token || !selectedResumeId) {
      setCuratedSkills([]);
      return;
    }
    void loadCuratedSkills(selectedResumeId);
  }, [token, selectedResumeId]);

  useEffect(() => {
    if (!token) {
      return;
    }
    void loadWarmupStatus();
    const timer = window.setInterval(() => {
      void loadWarmupStatus();
    }, 20000);
    return () => window.clearInterval(timer);
  }, [token]);

  useEffect(() => {
    if (!warmupStatus?.enabled || !warmupStatus.last_finished_at) {
      return;
    }
    const timer = window.setInterval(() => setNowTick(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [warmupStatus?.enabled, warmupStatus?.last_finished_at]);

  useEffect(() => {
    if (resumes.length === 0) {
      setSelectedResumeId(null);
      return;
    }

    if (selectedResumeId && resumes.some((resume) => resume.id === selectedResumeId)) {
      return;
    }

    const completed = resumes.find((resume) => resume.status === 'completed');
    setSelectedResumeId(completed ? completed.id : resumes[0].id);
  }, [resumes, selectedResumeId]);

  const visibleMatches = excludeFeedbackVacancies(matches, dislikedVacancies, selectedVacancies, hiddenMatchIds);

  const currentMatchRunId = visibleMatches[0]?.match_run_id ?? null;
  const matchRunIdRef = useRef<string | null>(null);
  matchRunIdRef.current = currentMatchRunId;
  const cardRefs = useRef<Map<number, HTMLElement>>(new Map());
  const dwellTrackerRef = useRef<ReturnType<typeof createDwellTracker> | null>(null);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof IntersectionObserver === 'undefined') {
      return;
    }
    const tracker = createDwellTracker({ getRunId: () => matchRunIdRef.current });
    dwellTrackerRef.current = tracker;
    return () => {
      tracker.dispose();
      dwellTrackerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const tracker = dwellTrackerRef.current;
    if (!tracker) return;
    const seen = new Set<number>();
    for (const match of visibleMatches) {
      const id = normalizeVacancyId(match.vacancy_id);
      seen.add(id);
      const el = cardRefs.current.get(id);
      if (el) tracker.observe(id, el);
    }
    for (const id of [...cardRefs.current.keys()]) {
      if (!seen.has(id)) {
        tracker.unobserve(id);
        cardRefs.current.delete(id);
      }
    }
  }, [visibleMatches]);

  function setPersistentJobId(jobId: string | null) {
    setCurrentJobId(jobId);
    try {
      if (jobId && jobId.trim()) {
        window.localStorage.setItem(LAST_JOB_ID_STORAGE_KEY, jobId);
      } else {
        window.localStorage.removeItem(LAST_JOB_ID_STORAGE_KEY);
      }
    } catch {
      // ignore storage issues
    }
  }

  function formatOpenAiUsage(usage: VacancyRecommendResponse['openai_usage'] | null): string {
    if (!usage) {
      return '';
    }
    return `OpenAI: ~$${usage.estimated_cost_usd.toFixed(4)} / $${usage.budget_usd.toFixed(2)}, токены: ${usage.total_tokens}, вызовов: ${usage.api_calls}.`;
  }

  function formatMetricsInfo(metrics: RecommendationJobStatusResponse['metrics']): string {
    return formatRecommendationMetrics(metrics);
  }

  function applyJobSnapshot(status: RecommendationJobStatusResponse) {
    const metrics = status.metrics || {};
    const sources = Array.isArray(metrics.sources) ? metrics.sources : [];
    const progress = Math.max(1, Math.min(100, Number(status.progress || 0)));
    setMatchingProgress(progress);
    setMatchingStage(stageLabel(status.stage));
    setOpenaiUsageMessage(formatOpenAiUsage(status.openai_usage));
    setLastMatchingQuery(status.query || '');
    setLastSources(sources);
    setCancelRequested(Boolean(status.cancel_requested));

    if (status.status === 'completed') {
      const visibleMatches = excludeFeedbackVacancies(
        status.matches || [],
        dislikedVacancies,
        selectedVacancies,
        hiddenMatchIds
      );
      setMatches(visibleMatches);
      const metricsInfo = formatMetricsInfo(metrics);
      const headline = formatRecommendationHeadline(visibleMatches.length);
      setMatchingMessage(metricsInfo ? `${headline} ${metricsInfo}` : headline);
      setMatchingProgress(100);
      setMatchingStage('Готово');
      return;
    }

    if (status.status === 'failed') {
      setMatchingMessage(status.error_message || 'Задача подбора завершилась с ошибкой.');
      setMatchingProgress(100);
      setMatchingStage('Ошибка');
      return;
    }

    setMatchingMessage('Подбор вакансий выполняется. Результат появится автоматически.');
  }

  function clearSession(nextMessage?: string) {
    clearSessionCtx(nextMessage);
    setResumes([]);
    setMatches([]);
    setHiddenMatchIds([]);
    setSelectedVacancies([]);
    setDislikedVacancies([]);
    setExpandedResumeIds({});
    setSelectedResumeId(null);
    setMatchingProgress(0);
    setMatchingStage('');
    setCancelRequested(false);
    setDashboardStats(null);
    setWarmupStatus(null);
    setOpenaiUsageMessage('');
    setLastMatchingQuery('');
    setLastSources([]);
    setUserPrefs(null);
    setProfileDraft(null);
    setProfileConfirmed(false);
    setProfileMessage('');
    setApplyingVacancyIds({});
    if (nextMessage) {
      setMessage(nextMessage);
    }
  }

  async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(options.headers || {})
      }
    });

    const knownJobId = currentJobId || readStoredJobId();
    if (response.status === 401) {
      const sessionMessage = knownJobId
        ? `Сессия истекла. Войдите снова — восстановим результат по Job ID: ${knownJobId}.`
        : 'Сессия истекла. Войдите снова.';
      clearSession(sessionMessage);
      throw new Error(sessionMessage);
    }

    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: 'Запрос не выполнен' }));
      const detail = payload.detail;
      if (detail && typeof detail === 'object' && 'error' in detail) {
        if (detail.error === 'resume_limit_exceeded') {
          throw new Error(
            `Достигнут лимит ${detail.limit ?? RESUME_LIMIT} профилей. Удалите один, чтобы загрузить новый.`
          );
        }
        throw new Error(detail.message || detail.error || 'Запрос не выполнен');
      }
      throw new Error(typeof detail === 'string' ? detail : 'Запрос не выполнен');
    }

    if (response.status === 204) {
      return null as T;
    }

    return response.json() as Promise<T>;
  }

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage('');

    try {
      if (authFormMode === 'reset') {
        if (!betaKey.trim()) {
          throw new Error('Введите код тестировщика');
        }
        await apiFetch('/api/auth/password/reset', {
          method: 'POST',
          body: JSON.stringify({ email, new_password: newPassword, beta_key: betaKey }),
          fallbackError: 'Не удалось обновить пароль'
        });
        setAuthFormMode('login');
        setPassword(newPassword);
        setNewPassword('');
        setMessage('Пароль обновлен. Войдите с новым паролем.');
        return;
      }

      if (authFormMode === 'register') {
        if (!betaKey.trim()) {
          throw new Error('Введите код тестировщика');
        }
        await apiFetch('/api/auth/register', {
          method: 'POST',
          body: JSON.stringify({ email, password, full_name: null, beta_key: betaKey }),
          fallbackError: 'Не удалось создать аккаунт'
        });
      }

      const auth = await apiFetch<{ access_token: string }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
        fallbackError: 'Не удалось войти'
      });
      // user details will be loaded by loadUserPrefs after token change
      setSession({ token: auth.access_token, user: { id: 0, email, full_name: null, is_admin: false } });
      setMessage('');
      return;
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Ошибка авторизации');
    } finally {
      setBusy(false);
    }
  }

  async function loadResumes(activeToken = token) {
    if (!activeToken) {
      return;
    }

    const response = await fetch(`${API_BASE_URL}/api/resumes`, {
      headers: { Authorization: `Bearer ${activeToken}` }
    });

    const knownJobId = currentJobId || readStoredJobId();
    if (response.status === 401) {
      const sessionMessage = knownJobId
        ? `Сессия истекла. Войдите снова — восстановим результат по Job ID: ${knownJobId}.`
        : 'Сессия истекла. Войдите снова.';
      clearSession(sessionMessage);
      return;
    }

    if (response.status === 401) {
      clearSession('Сессия истекла. Войдите снова.');
      return;
    }

    if (response.ok) {
      const data = (await response.json()) as Resume[];
      setResumes(data);
    }
  }

  // Keep the latest activateResumeProfile impl in a ref so the session context
  // always delegates to the current closure without re-registering on every render.
  const activateResumeProfileRef = useRef<(id: number) => Promise<void>>(
    () => Promise.resolve()
  );

  async function activateResumeProfile(resumeId: number) {
    const target = resumes.find((row) => row.id === resumeId);
    if (!target || target.is_active) {
      return;
    }
    setBusy(true);
    try {
      const updated = await request<Resume>(`/api/resumes/${resumeId}/activate`, {
        method: 'POST'
      });
      setResumes((current) =>
        current.map((row) =>
          row.id === updated.id
            ? { ...updated }
            : { ...row, is_active: false }
        )
      );
      setSelectedResumeId(updated.id);
      setMatches([]);
      setLastMatchingQuery('');
      setHiddenMatchIds([]);
      await Promise.all([loadSelectedVacancies(), loadDislikedVacancies()]);
      setMessage(`Активный профиль: ${resumeDisplayName(updated)}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось переключить профиль');
    } finally {
      setBusy(false);
    }
  }

  // Update the ref every render so the session wrapper always uses latest closure.
  activateResumeProfileRef.current = activateResumeProfile;

  // Register a stable wrapper with the session context once on mount.
  useEffect(() => {
    setActivateResumeProfile((id: number) => activateResumeProfileRef.current(id));
  }, [setActivateResumeProfile]);

  async function saveResumeLabel(resumeId: number, nextLabel: string) {
    const trimmed = nextLabel.trim().slice(0, RESUME_LABEL_MAX);
    const existing = resumes.find((row) => row.id === resumeId);
    if (!existing) {
      return;
    }
    if ((existing.label ?? '') === trimmed) {
      return;
    }
    try {
      const updated = await request<Resume>(`/api/resumes/${resumeId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label: trimmed })
      });
      setResumes((current) => current.map((row) => (row.id === updated.id ? updated : row)));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось сохранить метку профиля');
    }
  }

  async function loadSelectedVacancies() {
    try {
      const data = await request<VacancyMatch[]>('/api/vacancies/feedback/selected');
      setSelectedVacancies(data);
    } catch {
      setSelectedVacancies([]);
    }
  }

  async function loadCuratedSkills(resumeId: number) {
    try {
      const data = await request<CuratedSkillRead[]>(`/api/resumes/${resumeId}/skills/curate`);
      setCuratedSkills(data);
    } catch {
      setCuratedSkills([]);
    }
  }

  async function curateMatchSkill(
    match: VacancyMatch,
    skill: string,
    direction: CuratedDirection
  ) {
    if (!selectedResumeId) {
      return;
    }
    const trimmed = skill.trim();
    if (!trimmed) {
      return;
    }
    const key = `${match.vacancy_id}::${direction}::${trimmed.toLowerCase()}`;
    if (curatingSkillKey) {
      return;
    }
    setCuratingSkillKey(key);
    try {
      const payload = await request<CuratedSkillResponse>(
        `/api/resumes/${selectedResumeId}/skills/curate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            skill: trimmed,
            direction,
            vacancy_id: match.vacancy_id
          })
        }
      );
      setCuratedSkills((current) => {
        const rest = current.filter((row) => row.id !== payload.skill.id);
        return [payload.skill, ...rest];
      });
      if (payload.warn_sanity_check) {
        setMatchingMessage(
          'Отмечено много навыков за последний час — сверьтесь с резюме, чтобы подбор был точным.'
        );
      } else if (direction === 'added') {
        setMatchingMessage(`Добавлено в профиль: «${trimmed}». В следующем подборе учтём.`);
      } else {
        setMatchingMessage(`Отмечено как не моё: «${trimmed}». Уберём из «не хватает».`);
      }
    } catch (error) {
      setMatchingMessage(
        error instanceof Error ? error.message : 'Не удалось сохранить отметку. Попробуйте ещё раз.'
      );
    } finally {
      setCuratingSkillKey(null);
    }
  }

  async function uncurateSkill(skillId: number) {
    if (!selectedResumeId) {
      return;
    }
    const key = `uncurate::${skillId}`;
    if (curatingSkillKey) {
      return;
    }
    setCuratingSkillKey(key);
    try {
      await request<null>(
        `/api/resumes/${selectedResumeId}/skills/curate/${skillId}`,
        { method: 'DELETE' }
      );
      setCuratedSkills((current) => current.filter((row) => row.id !== skillId));
      setMatchingMessage('Отметка снята.');
    } catch (error) {
      setMatchingMessage(
        error instanceof Error ? error.message : 'Не удалось снять отметку.'
      );
    } finally {
      setCuratingSkillKey(null);
    }
  }

  async function loadUserPrefs() {
    try {
      const data = await request<UserRead>('/api/users/me');
      setUserPrefs({
        preferred_work_format: data.preferred_work_format,
        relocation_mode: data.relocation_mode,
        home_city: data.home_city,
        preferred_titles: data.preferred_titles,
        expected_salary_min: data.expected_salary_min,
        expected_salary_max: data.expected_salary_max,
        expected_salary_currency: data.expected_salary_currency
      });
      // Sync is_admin + canonical user identity into context
      if (token) {
        setSession({
          token,
          user: {
            id: data.id,
            email: data.email,
            full_name: data.full_name,
            is_admin: data.is_admin,
          },
        });
      }
    } catch {
      setUserPrefs(null);
    }
  }

  function updateProfileDraft(patch: Partial<ProfileDraft>) {
    setProfileDraft((current) => (current ? { ...current, ...patch } : current));
  }

  async function saveProfileAndRecommend() {
    if (!selectedResumeId || !profileDraft) {
      setProfileMessage('Сначала выберите резюме.');
      return;
    }
    const years = profileDraft.total_experience_years.trim();
    const yearsNumber = years === '' ? null : Number(years);
    if (yearsNumber !== null && (!Number.isFinite(yearsNumber) || yearsNumber < 0 || yearsNumber > 80)) {
      setProfileMessage('Годы опыта должны быть числом от 0 до 80.');
      return;
    }

    const topSkills = profileDraft.top_skills.map((skill) => skill.trim()).filter(Boolean);
    const homeCityTrimmed = profileDraft.home_city.trim();

    const analysisUpdates: Record<string, unknown> = {};
    if (profileDraft.target_role.trim()) analysisUpdates.target_role = profileDraft.target_role.trim();
    if (profileDraft.specialization.trim()) analysisUpdates.specialization = profileDraft.specialization.trim();
    if (profileDraft.seniority) analysisUpdates.seniority = profileDraft.seniority;
    if (yearsNumber !== null) analysisUpdates.total_experience_years = yearsNumber;
    if (topSkills.length > 0) analysisUpdates.top_skills = topSkills;

    const preferenceUpdates: Record<string, unknown> = {
      preferred_work_format: profileDraft.preferred_work_format,
      relocation_mode: profileDraft.relocation_mode,
      preferred_titles: profileDraft.preferred_titles
    };
    if (homeCityTrimmed) {
      preferenceUpdates.home_city = homeCityTrimmed;
    } else {
      preferenceUpdates.clear_home_city = true;
    }
    const parseSalaryInput = (raw: string): number | null => {
      const trimmed = raw.trim();
      if (!trimmed) return 0;
      const normalized = Number(trimmed.replace(/\s+/g, ''));
      if (!Number.isFinite(normalized) || normalized < 0 || normalized > 10_000_000) {
        return null;
      }
      return Math.round(normalized);
    };
    const parsedMin = parseSalaryInput(profileDraft.expected_salary_min);
    const parsedMax = parseSalaryInput(profileDraft.expected_salary_max);
    if (parsedMin === null || parsedMax === null) {
      setProfileMessage('Зарплата должна быть числом от 0 до 10 000 000.');
      return;
    }
    preferenceUpdates.expected_salary_min = parsedMin;
    preferenceUpdates.expected_salary_max = parsedMax;

    const body: Record<string, unknown> = {};
    if (Object.keys(analysisUpdates).length > 0) body.analysis_updates = analysisUpdates;
    body.preference_updates = preferenceUpdates;

    setProfileSaving(true);
    setProfileMessage('Сохраняем профиль...');
    try {
      const response = await request<{
        resume: Resume;
        preferences: UserPrefs;
      }>(`/api/resumes/${selectedResumeId}/profile-confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      setResumes((current) =>
        current.map((resume) => (resume.id === response.resume.id ? response.resume : resume))
      );
      setUserPrefs(response.preferences);
      setProfileConfirmed(true);
      setProfileMessage('Профиль сохранён. Запускаем подбор...');
      await refreshVacancyIndex();
    } catch (error) {
      setProfileMessage(error instanceof Error ? error.message : 'Не удалось сохранить профиль');
    } finally {
      setProfileSaving(false);
    }
  }

  async function loadDislikedVacancies() {
    try {
      const data = await request<VacancyMatch[]>('/api/vacancies/feedback/disliked');
      setDislikedVacancies(data);
    } catch {
      setDislikedVacancies([]);
    }
  }

  async function loadDashboardStats(resumeId: number | null) {
    try {
      const suffix = resumeId ? `?resume_id=${resumeId}` : '';
      const data = await request<DashboardStatsResponse>(`/api/dashboard/stats${suffix}`);
      setDashboardStats(data);
    } catch {
      setDashboardStats(null);
    }
  }

  async function loadWarmupStatus() {
    try {
      const data = await request<WarmupStatusResponse>('/api/system/vacancy-warmup');
      setWarmupStatus(data);
    } catch {
      setWarmupStatus(null);
    }
  }

  async function uploadResume(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) {
      setMessage('Выберите PDF или DOCX файл');
      return;
    }

    setBusy(true);
    setMessage('Анализируем резюме...');

    try {
      const formData = new FormData();
      formData.append('file', file);
      const resume = await request<Resume>('/api/resumes', { method: 'POST', body: formData });
      setResumes((current) => [resume, ...current]);
      setMessage(resume.status === 'completed' ? 'Анализ готов' : resume.error_message || 'Не удалось обработать резюме');
      setFile(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось загрузить резюме');
    } finally {
      setBusy(false);
    }
  }

  async function deleteResume(resumeId: number) {
    setBusy(true);
    setMessage('');

    try {
      await request<void>(`/api/resumes/${resumeId}`, { method: 'DELETE' });
      setResumes((current) => current.filter((resume) => resume.id !== resumeId));
      setExpandedResumeIds((current) => {
        const next = { ...current };
        delete next[resumeId];
        return next;
      });
      if (selectedResumeId === resumeId) {
        setMatches([]);
        setLastMatchingQuery('');
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось удалить резюме');
    } finally {
      setBusy(false);
    }
  }

  async function cancelRecommendationJob() {
    if (!currentJobId || cancelRequested) {
      return;
    }
    setCancelRequested(true);
    try {
      const snapshot = await request<RecommendationJobStatusResponse>(
        `/api/vacancies/recommend/${currentJobId}`,
        { method: 'DELETE' }
      );
      applyJobSnapshot(snapshot);
      setMatchingMessage('Останавливаем подбор...');
    } catch (error) {
      // Leave the flag set locally — the poll loop will eventually reflect
      // the cancelled state or surface an error. Any network hiccup here
      // shouldn't undo the user's intent.
      setMatchingMessage(
        error instanceof Error ? `Не удалось отправить отмену: ${error.message}` : 'Не удалось отправить отмену.'
      );
    }
  }

  async function refreshVacancyIndex() {
    if (!selectedResumeId) {
      setMatchingMessage('Выберите резюме для подбора.');
      return;
    }

    const startedAt = Date.now();
    let terminalStage: 'completed' | 'failed' | null = null;
    setMatchingBusy(true);
    setMatchingProgress(1);
    setMatchingStage('Задача в очереди...');
    setMatchingMessage('Запускаем задачу подбора...');
    setOpenaiUsageMessage('');
    setLastMatchingQuery('');
    setLastSources([]);
    setCancelRequested(false);

    try {
      const started = await request<{ job_id: string; status: string }>(`/api/vacancies/recommend/start/${selectedResumeId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          discover_count: 100,
          match_limit: 20,
          deep_scan: true,
          rf_only: true,
          use_prefetched_index: false,
          discover_if_few_matches: true,
          min_prefetched_matches: 5
        })
      });
      setPersistentJobId(started.job_id);

      while (true) {
        const elapsed = Date.now() - startedAt;
        if (elapsed > RECOMMEND_TIMEOUT_MS) {
          throw new Error('Превышено время ожидания задачи подбора. Попробуйте сузить запрос или повторить позже.');
        }

        const status = await request<RecommendationJobStatusResponse>(`/api/vacancies/recommend/status/${started.job_id}`);
        applyJobSnapshot(status);
        if (status.status === 'running' || status.status === 'queued') {
          setMatchingMessage(`Прогресс: ${formatMetricsInfo(status.metrics || {})}`);
        }

        if (status.openai_usage) {
          setOpenaiUsageMessage(
            `OpenAI: ~$${status.openai_usage.estimated_cost_usd.toFixed(4)} / $${status.openai_usage.budget_usd.toFixed(2)}, токены: ${status.openai_usage.total_tokens}, вызовов: ${status.openai_usage.api_calls}.`
          );
        }

        if (status.status === 'completed') {
          terminalStage = 'completed';
          break;
        }

        if (status.status === 'failed') {
          terminalStage = 'failed';
          break;
        }
        if (!status.active && (status.status === 'queued' || status.status === 'running')) {
          throw new Error('Фоновая задача перестала выполняться. Запустите подбор повторно.');
        }

        await sleep(1200);
      }
    } catch (error) {
      setMatchingMessage(error instanceof Error ? error.message : 'Не удалось выполнить подбор');
      setMatchingStage('Ошибка');
    } finally {
      const elapsed = Date.now() - startedAt;
      if (elapsed < MIN_PROGRESS_VISIBLE_MS) {
        await sleep(MIN_PROGRESS_VISIBLE_MS - elapsed);
      }
      if (terminalStage === 'completed') {
        setMatchingProgress(100);
        setMatchingStage('Готово');
      } else if (terminalStage === 'failed') {
        setMatchingProgress(100);
        setMatchingStage('Ошибка');
      }
      setMatchingBusy(false);
      await loadDashboardStats(selectedResumeId);
    }
  }

  async function restoreRecommendationState() {
    if (!token || matchingBusy) {
      return;
    }

    let snapshot: RecommendationJobStatusResponse | null = null;
    const storedJobId = readStoredJobId();

    if (storedJobId) {
      try {
        snapshot = await request<RecommendationJobStatusResponse>(`/api/vacancies/recommend/status/${storedJobId}`);
      } catch {
        snapshot = null;
      }
    }

    if (!snapshot) {
      try {
        snapshot = await request<RecommendationJobStatusResponse>('/api/vacancies/recommend/latest');
      } catch {
        snapshot = null;
      }
    }

    if (!snapshot) {
      return;
    }

    setPersistentJobId(snapshot.job_id);
    applyJobSnapshot(snapshot);

    if (snapshot.status !== 'running' && snapshot.status !== 'queued') {
      await loadDashboardStats(selectedResumeId);
      return;
    }

    setMatchingBusy(true);
    const startedAt = Date.now();
    let terminalStage: 'completed' | 'failed' | null = null;

    try {
      while (true) {
        const elapsed = Date.now() - startedAt;
        if (elapsed > RECOMMEND_TIMEOUT_MS) {
          throw new Error('Превышено время ожидания задачи подбора. Попробуйте обновить страницу.');
        }

        const status = await request<RecommendationJobStatusResponse>(`/api/vacancies/recommend/status/${snapshot.job_id}`);
        applyJobSnapshot(status);
        if (status.status === 'running' || status.status === 'queued') {
          setMatchingMessage(`Прогресс: ${formatMetricsInfo(status.metrics || {})}`);
        }
        if (status.status === 'completed') {
          terminalStage = 'completed';
          break;
        }
        if (status.status === 'failed') {
          terminalStage = 'failed';
          break;
        }
        if (!status.active && (status.status === 'queued' || status.status === 'running')) {
          throw new Error('Фоновая задача остановилась. Запустите подбор заново.');
        }
        await sleep(1200);
      }
    } catch (error) {
      setMatchingMessage(error instanceof Error ? error.message : 'Не удалось восстановить статус подбора.');
      setMatchingStage('Ошибка');
    } finally {
      if (terminalStage === 'completed') {
        setMatchingProgress(100);
        setMatchingStage('Готово');
      } else if (terminalStage === 'failed') {
        setMatchingProgress(100);
        setMatchingStage('Ошибка');
      }
      setMatchingBusy(false);
      await loadDashboardStats(selectedResumeId);
    }
  }

  async function dislikeVacancy(vacancy: VacancyMatch) {
    setMatchingBusy(true);
    const vacancyId = normalizeVacancyId(vacancy.vacancy_id);
    setHiddenMatchIds((current) => (current.includes(vacancyId) ? current : [vacancyId, ...current]));
    setMatches((current) => removeVacancyMatchEntry(current, vacancy));
    try {
      await request<{ vacancy_id: number; disliked: boolean; liked: boolean }>('/api/vacancies/feedback/dislike', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vacancy_id: vacancy.vacancy_id })
      });
      setMatches((current) => removeVacancyMatchEntry(current, vacancy));
      setSelectedVacancies((current) => removeVacancyFromList(current, vacancyId));
      setDislikedVacancies((current) => {
        if (current.some((item) => normalizeVacancyId(item.vacancy_id) === vacancyId)) {
          return current;
        }
        return [vacancy, ...current];
      });
      setMatchingMessage('Вакансия скрыта. В следующих подборах она больше не будет показываться.');
    } catch (error) {
      setMatchingMessage(error instanceof Error ? error.message : 'Не удалось скрыть вакансию');
    } finally {
      setMatchingBusy(false);
      await loadDashboardStats(selectedResumeId);
    }
  }

  async function applyToVacancy(vacancy: VacancyMatch) {
    if (!token) {
      return;
    }
    const vacancyId = normalizeVacancyId(vacancy.vacancy_id);
    if (applyingVacancyIds[vacancyId]) {
      return;
    }
    setApplyingVacancyIds((current) => ({ ...current, [vacancyId]: true }));
    try {
      const response = await fetch(`${API_BASE_URL}/api/applications`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ vacancy_id: vacancy.vacancy_id, status: 'applied' }),
      });
      if (response.status === 401) {
        clearSession('Сессия истекла. Войдите снова.');
        return;
      }
      const payload = await response.json().catch(() => ({} as Record<string, unknown>));
      if (response.status === 201) {
        setMatchingMessage(
          `Создан отклик на «${vacancy.title || 'вакансию'}». Найдите её в разделе «Мои отклики».`
        );
      } else if (response.status === 409) {
        const detail = (payload as { detail?: { application_id?: number; message?: string } }).detail;
        const applicationId =
          detail && typeof detail === 'object' && typeof detail.application_id === 'number'
            ? detail.application_id
            : null;
        setMatchingMessage(
          applicationId
            ? `По этой вакансии уже есть отклик (#${applicationId}). Откройте его в «Моих откликах».`
            : 'По этой вакансии уже есть отклик.'
        );
      } else {
        const message =
          (payload as { detail?: unknown }).detail && typeof (payload as { detail?: unknown }).detail === 'string'
            ? String((payload as { detail?: unknown }).detail)
            : 'Не удалось создать отклик.';
        setMatchingMessage(message);
      }
    } catch (error) {
      setMatchingMessage(error instanceof Error ? error.message : 'Не удалось создать отклик.');
    } finally {
      setApplyingVacancyIds((current) => {
        const next = { ...current };
        delete next[vacancyId];
        return next;
      });
    }
  }

  async function likeVacancy(vacancy: VacancyMatch) {
    setMatchingBusy(true);
    const vacancyId = normalizeVacancyId(vacancy.vacancy_id);
    setHiddenMatchIds((current) => (current.includes(vacancyId) ? current : [vacancyId, ...current]));
    setMatches((current) => removeVacancyMatchEntry(current, vacancy));
    try {
      await request<{ vacancy_id: number; disliked: boolean; liked: boolean }>('/api/vacancies/feedback/like', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vacancy_id: vacancy.vacancy_id })
      });
      setMatches((current) => removeVacancyMatchEntry(current, vacancy));
      setSelectedVacancies((current) => {
        if (current.some((item) => normalizeVacancyId(item.vacancy_id) === vacancyId)) {
          return current;
        }
        return [vacancy, ...current];
      });
      setDislikedVacancies((current) => removeVacancyFromList(current, vacancyId));
      setMatchingMessage('Вакансия добавлена в отобранные и будет учитываться в следующих подборках.');
    } catch (error) {
      setMatchingMessage(error instanceof Error ? error.message : 'Не удалось добавить вакансию в отобранные');
    } finally {
      setMatchingBusy(false);
      await loadDashboardStats(selectedResumeId);
    }
  }

  async function unlikeVacancy(vacancyId: number) {
    setMatchingBusy(true);
    const normalizedVacancyId = normalizeVacancyId(vacancyId);
    try {
      await request<{ vacancy_id: number; disliked: boolean; liked: boolean }>('/api/vacancies/feedback/unlike', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vacancy_id: vacancyId })
      });
      setSelectedVacancies((current) => removeVacancyFromList(current, normalizedVacancyId));
      setHiddenMatchIds((current) => current.filter((item) => item !== normalizedVacancyId));
    } catch (error) {
      setMatchingMessage(error instanceof Error ? error.message : 'Не удалось убрать вакансию из отобранных');
    } finally {
      setMatchingBusy(false);
      await loadDashboardStats(selectedResumeId);
    }
  }

  async function undislikeVacancy(vacancyId: number) {
    setMatchingBusy(true);
    const normalizedVacancyId = normalizeVacancyId(vacancyId);
    try {
      await request<{ vacancy_id: number; disliked: boolean; liked: boolean }>('/api/vacancies/feedback/undislike', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ vacancy_id: vacancyId })
      });
      let restored: VacancyMatch | null = null;
      setDislikedVacancies((current) => {
        const found = current.find((item) => normalizeVacancyId(item.vacancy_id) === normalizedVacancyId) || null;
        restored = found;
        return removeVacancyFromList(current, normalizedVacancyId);
      });
      if (restored) {
        setSelectedVacancies((current) => {
          if (current.some((item) => normalizeVacancyId(item.vacancy_id) === normalizedVacancyId)) {
            return current;
          }
          return [restored as VacancyMatch, ...current];
        });
      } else {
        await loadSelectedVacancies();
      }
      setHiddenMatchIds((current) => current.filter((item) => item !== normalizedVacancyId));
      setMatchingMessage('Минус снят. Вакансия перенесена в отобранные.');
    } catch (error) {
      setMatchingMessage(error instanceof Error ? error.message : 'Не удалось снять минус с вакансии');
    } finally {
      setMatchingBusy(false);
      await loadDashboardStats(selectedResumeId);
    }
  }

  function logout() {
    clearSession();
  }

  function toggleResumeDetails(resumeId: number) {
    setExpandedResumeIds((current) => ({ ...current, [resumeId]: !current[resumeId] }));
  }

  return (
    <main className="page">
      <section className="main">
        <div className="headline">
          <div>
            <span className="hero-kicker">AI-профиль кандидата</span>
            <h1>Умный HR-помощник для анализа резюме</h1>
            <p>Загрузите резюме и запускайте целевой подбор вакансий одной кнопкой. В выдачу попадают только отфильтрованные вакансии.</p>
            <div className="hero-tags">
              <span>PDF и DOCX</span>
              <span>Qdrant matching</span>
              <span>OpenAI анализ</span>
            </div>
          </div>
        </div>

        {!token ? (
          <section className="panel">
            <h2>
              {authFormMode === 'login'
                ? 'Вход в кабинет'
                : authFormMode === 'register'
                  ? 'Регистрация нового пользователя'
                  : 'Восстановление пароля'}
            </h2>
            <form className="form" onSubmit={handleAuth}>
              <input
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="Email"
                type="email"
                autoComplete="email"
              />
              {authFormMode === 'reset' ? (
                <input
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                  placeholder="Новый пароль (минимум 8 символов)"
                  type="password"
                  autoComplete="new-password"
                />
              ) : (
                <input
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder={
                    authFormMode === 'register' ? 'Пароль (минимум 8 символов)' : 'Пароль'
                  }
                  type="password"
                  autoComplete={authFormMode === 'register' ? 'new-password' : 'current-password'}
                />
              )}
              {authFormMode !== 'login' ? (
                <input
                  value={betaKey}
                  onChange={(event) => setBetaKey(event.target.value)}
                  placeholder="Ключ бета-тестера"
                  type="password"
                  autoComplete="off"
                />
              ) : null}
              <button className="primary" disabled={busy}>
                {authFormMode === 'login'
                  ? 'Войти'
                  : authFormMode === 'register'
                    ? 'Зарегистрироваться'
                    : 'Сбросить пароль'}
              </button>
              {authFormMode === 'login' ? (
                <>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => {
                      setAuthFormMode('register');
                      setMessage('');
                    }}
                  >
                    Нет аккаунта? Зарегистрироваться
                  </button>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => {
                      setAuthFormMode('reset');
                      setMessage('');
                    }}
                  >
                    Забыли пароль?
                  </button>
                </>
              ) : (
                <button
                  className="secondary"
                  type="button"
                  onClick={() => {
                    setAuthFormMode('login');
                    setMessage('');
                  }}
                >
                  Назад ко входу
                </button>
              )}
            </form>
            {message ? <p className="message">{message}</p> : null}
          </section>
        ) : (
          <section className="workspace">
            <aside className="panel">
              <h2>Загрузка резюме</h2>
              <p className="panel-note">
                Поддерживаются PDF и DOCX. Можно хранить до {RESUME_LIMIT} профилей —
                например, IC и менеджерский — и переключаться между ними.
              </p>
              <form className="form" onSubmit={uploadResume}>
                <input
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  disabled={busy || resumes.length >= RESUME_LIMIT}
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                />
                <button
                  className="primary"
                  disabled={busy || resumes.length >= RESUME_LIMIT}
                >
                  Проанализировать
                </button>
                {resumes.length >= RESUME_LIMIT ? (
                  <p className="panel-note">
                    Достигнут лимит {RESUME_LIMIT} профилей. Удалите один, чтобы загрузить новый.
                  </p>
                ) : null}
              </form>
              {message ? <p className="message">{message}</p> : null}

              <Card className="mt-4">
                <CardHeader className="pb-2">
                  <CardTitle className="text-[var(--text-base)] font-semibold text-[var(--color-ink)]">
                    Моя воронка
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  {(() => {
                    const funnel = dashboardStats?.funnel;
                    const nextEtaMs = funnel?.next_warmup_eta
                      ? new Date(funnel.next_warmup_eta).getTime() - nowTick
                      : null;
                    const showCountdown =
                      warmupStatus?.enabled &&
                      funnel?.next_warmup_eta != null &&
                      nextEtaMs !== null &&
                      nextEtaMs > 0;
                    return (
                      <>
                        <div className="flex justify-between items-baseline">
                          <span className="text-[var(--text-sm)] text-[var(--color-ink-secondary)]">
                            Проанализировано вакансий
                          </span>
                          <span className="text-[var(--text-sm)] font-medium text-[var(--color-ink)]">
                            {funnel ? funnel.analyzed_count : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between items-baseline">
                          <span className="text-[var(--text-sm)] text-[var(--color-ink-secondary)]">
                            Отобрано
                          </span>
                          <span className="text-[var(--text-sm)] font-medium text-[var(--color-ink)]">
                            {funnel && (funnel.selected_count > 0 || funnel.matched_count > 0)
                              ? `${funnel.selected_count} из ${funnel.matched_count} совпадений`
                              : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between items-baseline">
                          <span className="text-[var(--text-sm)] text-[var(--color-ink-secondary)]">
                            Последний поиск
                          </span>
                          <span className="text-[var(--text-sm)] font-medium text-[var(--color-ink)]">
                            {funnel ? formatRelativeTimeRu(funnel.last_search_at) : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between items-baseline">
                          <span className="text-[var(--text-sm)] text-[var(--color-ink-secondary)]">
                            Следующее обновление
                          </span>
                          <span className="text-[var(--text-sm)] font-medium text-[var(--color-ink)]">
                            {warmupStatus?.running
                              ? 'идёт сейчас'
                              : showCountdown
                              ? formatCountdown(nextEtaMs as number)
                              : '—'}
                          </span>
                        </div>
                        {isAdmin ? (
                          <div className="mt-1 pt-2 border-t border-[var(--color-border)]">
                            <Link
                              href="/admin"
                              className="text-[var(--text-sm)] text-[var(--color-ink-muted)] hover:text-[var(--color-ink-secondary)] transition-colors"
                            >
                              Админ-панель →
                            </Link>
                          </div>
                        ) : null}
                      </>
                    );
                  })()}
                </CardContent>
              </Card>
            </aside>

            <div className="workspace-main">
              <section className="panel">
                <h2>Мое резюме</h2>
                <div className="resume-list">
                  {resumes.length === 0 ? <p className="empty-state">Пока нет загруженных резюме.</p> : null}
                  {resumes.map((resume) => (
                    <article
                      className={`resume-item${resume.is_active ? ' resume-item-active' : ''}`}
                      key={resume.id}
                    >
                      <div className="resume-item-head">
                        <div>
                          <h3>
                            {resume.original_filename}
                            {resume.is_active ? <span className="resume-active-tag">активный</span> : null}
                          </h3>
                          <span className={`status ${resume.status}`}>{statusLabels[resume.status] || resume.status}</span>
                        </div>
                        <div className="resume-actions">
                          {!resume.is_active ? (
                            <button
                              className="secondary"
                              disabled={busy}
                              onClick={() => void activateResumeProfile(resume.id)}
                            >
                              Сделать активным
                            </button>
                          ) : null}
                          <button className="secondary resume-toggle" disabled={busy} onClick={() => toggleResumeDetails(resume.id)}>
                            {expandedResumeIds[resume.id] ? 'Свернуть' : 'Показать детали'}
                          </button>
                          <button className="danger" disabled={busy} onClick={() => void deleteResume(resume.id)}>
                            Удалить
                          </button>
                        </div>
                      </div>
                      <label className="field resume-label-field">
                        <span>Короткое имя профиля</span>
                        <input
                          type="text"
                          maxLength={RESUME_LABEL_MAX}
                          defaultValue={resume.label ?? ''}
                          placeholder='Например: "IC Staff" или "Mgmt"'
                          disabled={busy}
                          onBlur={(event) => void saveResumeLabel(resume.id, event.target.value)}
                        />
                      </label>
                      {resume.error_message ? <p className="message">{resume.error_message}</p> : null}
                      {resume.analysis && expandedResumeIds[resume.id] ? <Analysis data={resume.analysis} /> : null}
                    </article>
                  ))}
                </div>
              </section>

              {profileDraft ? (
                <section className="panel confirm-card">
                  <h2>Мы поняли тебя так и что ты ищешь</h2>
                  <p className="panel-note">
                    Проверь, что анализ резюме не съехал, и задай ориентир подбора. Кнопка ниже
                    сохранит оба раздела и запустит поиск.
                  </p>

                  <div className="profile-section">
                    <h3>Мы поняли тебя так</h3>
                    <div className="profile-grid">
                      <label className="field">
                        <span>Роль</span>
                        <input
                          type="text"
                          value={profileDraft.target_role}
                          maxLength={200}
                          onChange={(event) =>
                            updateProfileDraft({ target_role: event.target.value })
                          }
                          placeholder="Senior Backend Engineer"
                        />
                      </label>
                      <label className="field">
                        <span>Специализация</span>
                        <input
                          type="text"
                          value={profileDraft.specialization}
                          maxLength={200}
                          onChange={(event) =>
                            updateProfileDraft({ specialization: event.target.value })
                          }
                          placeholder="API, platform, data"
                        />
                      </label>
                      <label className="field">
                        <span>Грейд</span>
                        <select
                          value={profileDraft.seniority}
                          onChange={(event) =>
                            updateProfileDraft({
                              seniority: (event.target.value as Seniority | '') || ''
                            })
                          }
                        >
                          <option value="">Не выбран</option>
                          {SENIORITY_OPTIONS.map((option) => (
                            <option key={option.value} value={option.value}>
                              {option.label}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label className="field">
                        <span>Годы опыта</span>
                        <input
                          type="number"
                          min="0"
                          max="80"
                          step="0.5"
                          value={profileDraft.total_experience_years}
                          onChange={(event) =>
                            updateProfileDraft({ total_experience_years: event.target.value })
                          }
                        />
                      </label>
                    </div>
                    <div className="field">
                      <span>Топ-3 скилла</span>
                      <div className="profile-skill-row">
                        {[0, 1, 2].map((index) => (
                          <input
                            key={`skill-${index}`}
                            type="text"
                            maxLength={100}
                            value={profileDraft.top_skills[index] || ''}
                            onChange={(event) => {
                              const next = [...profileDraft.top_skills];
                              while (next.length <= index) next.push('');
                              next[index] = event.target.value;
                              updateProfileDraft({ top_skills: next });
                            }}
                            placeholder={index === 0 ? 'Python' : index === 1 ? 'FastAPI' : 'PostgreSQL'}
                          />
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="profile-section">
                    <h3>Что ищешь</h3>
                    <div className="field">
                      <span>Формат работы</span>
                      <div className="radio-row">
                        {WORK_FORMAT_OPTIONS.map((option) => (
                          <label key={option.value} className="radio-chip">
                            <input
                              type="radio"
                              name="work-format"
                              value={option.value}
                              checked={profileDraft.preferred_work_format === option.value}
                              onChange={() =>
                                updateProfileDraft({ preferred_work_format: option.value })
                              }
                            />
                            <span>{option.label}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="field">
                      <span>Готовность к переезду</span>
                      <div className="radio-row">
                        <label className="radio-chip">
                          <input
                            type="radio"
                            name="relocation-mode"
                            value="home_only"
                            checked={profileDraft.relocation_mode === 'home_only'}
                            onChange={() => updateProfileDraft({ relocation_mode: 'home_only' })}
                          />
                          <span>Только в моём городе</span>
                        </label>
                        <label className="radio-chip">
                          <input
                            type="radio"
                            name="relocation-mode"
                            value="any_city"
                            checked={profileDraft.relocation_mode === 'any_city'}
                            onChange={() => updateProfileDraft({ relocation_mode: 'any_city' })}
                          />
                          <span>Открыт к переезду</span>
                        </label>
                      </div>
                    </div>

                    {profileDraft.relocation_mode === 'home_only' ? (
                      <label className="field">
                        <span>Мой город</span>
                        <input
                          type="text"
                          maxLength={120}
                          value={profileDraft.home_city}
                          onChange={(event) =>
                            updateProfileDraft({ home_city: event.target.value })
                          }
                          placeholder="Москва"
                        />
                      </label>
                    ) : null}

                    <label className="field">
                      <span>
                        Желаемые названия вакансий (до 10).{' '}
                        <em className="field-hint">
                          не исключает другие — просто поднимает совпадающие в выдаче.
                        </em>
                      </span>
                      <textarea
                        rows={3}
                        value={profileDraft.preferred_titles.join(', ')}
                        onChange={(event) => {
                          const parts = event.target.value
                            .split(/[,\n]/)
                            .map((title) => title.trim())
                            .filter(Boolean)
                            .slice(0, 10);
                          updateProfileDraft({ preferred_titles: parts });
                        }}
                        placeholder="Senior Backend Engineer, Python Developer"
                      />
                    </label>

                    <div className="field">
                      <span>
                        Ожидаемая зарплата, ₽/мес.{' '}
                        <em className="field-hint">
                          мы не скроем варианты ниже — просто подвинем их вниз.
                        </em>
                      </span>
                      <div className="salary-range-row">
                        <input
                          type="number"
                          min={0}
                          max={10_000_000}
                          step={5000}
                          value={profileDraft.expected_salary_min}
                          onChange={(event) =>
                            updateProfileDraft({ expected_salary_min: event.target.value })
                          }
                          placeholder="от"
                        />
                        <span className="salary-range-sep">—</span>
                        <input
                          type="number"
                          min={0}
                          max={10_000_000}
                          step={5000}
                          value={profileDraft.expected_salary_max}
                          onChange={(event) =>
                            updateProfileDraft({ expected_salary_max: event.target.value })
                          }
                          placeholder="до"
                        />
                      </div>
                    </div>
                  </div>

                  <button
                    className="primary profile-confirm-button"
                    disabled={profileSaving || matchingBusy}
                    onClick={() => void saveProfileAndRecommend()}
                  >
                    {profileSaving ? 'Сохраняем...' : 'Подтвердить и найти работу'}
                  </button>
                  {profileMessage ? <p className="message">{profileMessage}</p> : null}
                  {curatedSkills.length > 0 ? (
                    <div className="curated-block">
                      {curatedSkills.some((row) => row.direction === 'added') ? (
                        <div className="curated-group">
                          <p className="curated-title">Добавлено вручную</p>
                          <ul className="curated-list">
                            {curatedSkills
                              .filter((row) => row.direction === 'added')
                              .map((row) => (
                                <li key={`curated-added-${row.id}`}>
                                  <span>{row.skill_text}</span>
                                  <button
                                    type="button"
                                    className="fit-micro-btn fit-micro-undo"
                                    title="Снять отметку"
                                    aria-label={`Снять отметку с «${row.skill_text}»`}
                                    disabled={Boolean(curatingSkillKey)}
                                    onClick={() => void uncurateSkill(row.id)}
                                  >
                                    ✕
                                  </button>
                                </li>
                              ))}
                          </ul>
                        </div>
                      ) : null}
                      {curatedSkills.some((row) => row.direction === 'rejected') ? (
                        <div className="curated-group">
                          <p className="curated-title">Отмечено как не моё</p>
                          <ul className="curated-list">
                            {curatedSkills
                              .filter((row) => row.direction === 'rejected')
                              .map((row) => (
                                <li key={`curated-rejected-${row.id}`}>
                                  <span>{row.skill_text}</span>
                                  <button
                                    type="button"
                                    className="fit-micro-btn fit-micro-undo"
                                    title="Снять отметку"
                                    aria-label={`Снять отметку с «${row.skill_text}»`}
                                    disabled={Boolean(curatingSkillKey)}
                                    onClick={() => void uncurateSkill(row.id)}
                                  >
                                    ✕
                                  </button>
                                </li>
                              ))}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                </section>
              ) : null}

              <section className="panel">
                <h2>Подбор вакансий</h2>
                <div className="inline-form">
                  <select
                    value={selectedResumeId ?? ''}
                    onChange={(event) => setSelectedResumeId(event.target.value ? Number(event.target.value) : null)}
                  >
                    <option value="">Выберите резюме</option>
                    {resumes.map((resume) => (
                      <option key={resume.id} value={resume.id}>
                        #{resume.id} {resume.original_filename}
                      </option>
                    ))}
                  </select>
                  <button className="primary" onClick={refreshVacancyIndex} disabled={matchingBusy}>
                    Обновить подбор
                  </button>
                </div>
                {matchingBusy || matchingProgress > 0 ? (
                  <div className="progress-box">
                    <div className="progress-head">
                      <span>{matchingStage || 'Идет выполнение...'}</span>
                      <span>{matchingProgress}%</span>
                    </div>
                    <div className="progress-track">
                      <div className="progress-fill" style={{ width: `${matchingProgress}%` }} />
                    </div>
                    {matchingBusy && currentJobId ? (
                      <div className="progress-actions">
                        <button
                          className="danger progress-cancel"
                          disabled={cancelRequested}
                          onClick={() => void cancelRecommendationJob()}
                        >
                          {cancelRequested ? 'Останавливаем...' : 'Отменить'}
                        </button>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {matchingMessage ? <p className="message">{matchingMessage}</p> : null}
                {currentJobId ? <p className="panel-note">Job ID: {currentJobId}</p> : null}
                {openaiUsageMessage ? <p className="panel-note">{openaiUsageMessage}</p> : null}
                {lastMatchingQuery ? <p className="panel-note">Поисковый запрос: {lastMatchingQuery}</p> : null}
                {lastSources.length > 0 ? (
                  <details className="sources-box">
                    <summary>Источники текущего запуска ({lastSources.length})</summary>
                    <ul>
                      {lastSources.map((sourceUrl) => (
                        <li key={sourceUrl}>
                          <a href={sourceUrl} target="_blank" rel="noreferrer">
                            {sourceUrl}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : null}
                <div className="vacancy-list">
                  {visibleMatches.length === 0 ? <p className="empty-state">После запуска здесь появятся подходящие вакансии.</p> : null}
                  {visibleMatches.map((match, matchIndex) => {
                    const showTierDivider =
                      match.tier === 'maybe' &&
                      (matchIndex === 0 || visibleMatches[matchIndex - 1]?.tier !== 'maybe');
                    const matchedSkills = matchedSkillsFromMatch(match);
                    const matchedRequirements = matchedRequirementsFromMatch(match);
                    const missingRequirements = missingRequirementsFromMatch(match);
                    const matchedEntries = matchedRequirements.length > 0 ? matchedRequirements : matchedSkills;
                    const curatedForResume = curatedSkills;
                    const curatedAddedLower = new Set(
                      curatedForResume.filter((row) => row.direction === 'added').map((row) => row.skill_text.toLowerCase())
                    );
                    const curatedRejectedLower = new Set(
                      curatedForResume.filter((row) => row.direction === 'rejected').map((row) => row.skill_text.toLowerCase())
                    );
                    const locallyAddedForMatch = curatedForResume
                      .filter(
                        (row) =>
                          row.direction === 'added' &&
                          row.source_vacancy_id === match.vacancy_id &&
                          !matchedEntries.some((item) => item.toLowerCase() === row.skill_text.toLowerCase())
                      )
                      .map((row) => row.skill_text);
                    const visibleMissing = missingRequirements.filter(
                      (item) =>
                        !curatedAddedLower.has(item.toLowerCase()) &&
                        !curatedRejectedLower.has(item.toLowerCase())
                    );
                    const isCurating = (skill: string, direction: CuratedDirection) =>
                      curatingSkillKey === `${match.vacancy_id}::${direction}::${skill.toLowerCase()}`;
                    return (
                    <Fragment key={match.vacancy_id}>
                    {showTierDivider ? (
                      <div className="vacancy-tier-divider">
                        <h3 className="vacancy-tier-title">Может подойти — проверь</h3>
                        <p className="vacancy-tier-hint">
                          Эти вакансии слабее совпадают по профилю, но иногда среди них находится удачное предложение.
                        </p>
                      </div>
                    ) : null}
                    <article
                      className="vacancy-item"
                      data-vacancy-id={normalizeVacancyId(match.vacancy_id)}
                      ref={(el) => {
                        const id = normalizeVacancyId(match.vacancy_id);
                        if (el) {
                          cardRefs.current.set(id, el);
                        } else {
                          cardRefs.current.delete(id);
                        }
                      }}
                    >
                      <h3>{match.title}</h3>
                      <p className="meta">
                        {match.company || 'Компания не указана'}
                        {' • '}
                        {match.location || 'Локация не указана'}
                      </p>
                      <p className="match-score">Релевантность: {scoreToPercent(match.similarity_score)}</p>
                      {(() => {
                        const badge = renderSalaryBadge(match);
                        if (!badge) return null;
                        const fitClass = badge.fit ? `salary-fit-${badge.fit}` : '';
                        const fitLabel =
                          badge.fit === 'below'
                            ? ' (ниже ожиданий)'
                            : badge.fit === 'above'
                              ? ' (выше ожиданий)'
                              : '';
                        return (
                          <p className={`match-salary ${fitClass}`.trim()}>
                            <span className="match-salary-label">Зарплата:</span> {badge.text}
                            {fitLabel}
                          </p>
                        );
                      })()}
                      {reasonFromMatch(match) ? (
                        <p className="match-reason">
                          <span className="match-reason-label">Почему показали:</span>{' '}
                          {reasonFromMatch(match)}
                        </p>
                      ) : null}
                      <div className="fit-grid">
                        <div className="fit-box fit-matched">
                          <p className="fit-title">Ты подходишь</p>
                          {matchedEntries.length > 0 || locallyAddedForMatch.length > 0 ? (
                            <ul>
                              {matchedEntries.map((item) => (
                                <li key={`${match.vacancy_id}-match-${item}`}>{item}</li>
                              ))}
                              {locallyAddedForMatch.map((item) => (
                                <li
                                  key={`${match.vacancy_id}-match-added-${item}`}
                                  className="fit-item-added"
                                >
                                  {item}
                                  <span className="curated-badge" title="Добавлено вручную">
                                    ✓
                                  </span>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="fit-empty">совпадение по ключевым словам в описании</p>
                          )}
                        </div>
                        <div className="fit-box fit-missing">
                          <p className="fit-title">Чего не хватает</p>
                          {visibleMissing.length > 0 ? (
                            <ul>
                              {visibleMissing.map((item) => (
                                <li
                                  key={`${match.vacancy_id}-miss-${item}`}
                                  className="fit-missing-item"
                                >
                                  <span className="fit-missing-text">{item}</span>
                                  <span className="fit-missing-actions">
                                    <button
                                      type="button"
                                      className="fit-micro-btn fit-micro-add"
                                      title="Добавить в профиль"
                                      aria-label={`Добавить навык «${item}» в профиль`}
                                      disabled={
                                        !selectedResumeId ||
                                        matchingBusy ||
                                        Boolean(curatingSkillKey)
                                      }
                                      onClick={() => void curateMatchSkill(match, item, 'added')}
                                    >
                                      {isCurating(item, 'added') ? '…' : '✓'}
                                    </button>
                                    <button
                                      type="button"
                                      className="fit-micro-btn fit-micro-reject"
                                      title="Отметить как не моё"
                                      aria-label={`Отметить «${item}» как не моё`}
                                      disabled={
                                        !selectedResumeId ||
                                        matchingBusy ||
                                        Boolean(curatingSkillKey)
                                      }
                                      onClick={() => void curateMatchSkill(match, item, 'rejected')}
                                    >
                                      {isCurating(item, 'rejected') ? '…' : '✗'}
                                    </button>
                                  </span>
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <p className="fit-empty">совпадение по всем указанным требованиям</p>
                          )}
                        </div>
                      </div>
                      <div className="vacancy-actions">
                        <a
                          href={match.source_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={() =>
                            trackClick({
                              vacancy_id: normalizeVacancyId(match.vacancy_id),
                              click_kind: 'open_source',
                              match_run_id: match.match_run_id ?? null,
                              resume_id: selectedResumeId ?? null,
                              position: matchIndex,
                            })
                          }
                        >
                          Открыть источник
                        </a>
                        <button
                          className="primary"
                          disabled={
                            matchingBusy ||
                            Boolean(applyingVacancyIds[normalizeVacancyId(match.vacancy_id)])
                          }
                          onClick={() => {
                            trackClick({
                              vacancy_id: normalizeVacancyId(match.vacancy_id),
                              click_kind: 'apply',
                              match_run_id: match.match_run_id ?? null,
                              resume_id: selectedResumeId ?? null,
                              position: matchIndex,
                            });
                            void applyToVacancy(match);
                          }}
                        >
                          {applyingVacancyIds[normalizeVacancyId(match.vacancy_id)]
                            ? 'Создаём…'
                            : 'Откликнуться'}
                        </button>
                        <button
                          className="secondary"
                          disabled={matchingBusy}
                          onClick={() => {
                            trackClick({
                              vacancy_id: normalizeVacancyId(match.vacancy_id),
                              click_kind: 'like',
                              match_run_id: match.match_run_id ?? null,
                              resume_id: selectedResumeId ?? null,
                              position: matchIndex,
                            });
                            void likeVacancy(match);
                          }}
                        >
                          Плюс
                        </button>
                        <button
                          className="danger"
                          disabled={matchingBusy}
                          onClick={() => {
                            trackClick({
                              vacancy_id: normalizeVacancyId(match.vacancy_id),
                              click_kind: 'dislike',
                              match_run_id: match.match_run_id ?? null,
                              resume_id: selectedResumeId ?? null,
                              position: matchIndex,
                            });
                            void dislikeVacancy(match);
                          }}
                        >
                          Минус
                        </button>
                      </div>
                    </article>
                    </Fragment>
                    );
                  })}
                </div>
              </section>

              <section className="panel">
                <h2>Отобранные вакансии</h2>
                <div className="vacancy-list">
                  {selectedVacancies.length === 0 ? <p className="empty-state">Пока нет отобранных. Нажмите Плюс в подборке.</p> : null}
                  {selectedVacancies.map((item) => (
                    <article className="vacancy-item" key={`selected-${item.vacancy_id}`}>
                      <h3>{item.title}</h3>
                      <p className="meta">
                        {item.company || 'Компания не указана'}
                        {' • '}
                        {item.location || 'Локация не указана'}
                      </p>
                      <div className="vacancy-actions">
                        <a href={item.source_url} target="_blank" rel="noreferrer">
                          Открыть источник
                        </a>
                        <button className="secondary" disabled={matchingBusy} onClick={() => void unlikeVacancy(item.vacancy_id)}>
                          Убрать
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </section>

              <section className="panel">
                <h2>Минусованные вакансии</h2>
                <div className="vacancy-list">
                  {dislikedVacancies.length === 0 ? <p className="empty-state">Пока нет минусованных вакансий.</p> : null}
                  {dislikedVacancies.map((item) => (
                    <article className="vacancy-item" key={`disliked-${item.vacancy_id}`}>
                      <h3>{item.title}</h3>
                      <p className="meta">
                        {item.company || 'Компания не указана'}
                        {' • '}
                        {item.location || 'Локация не указана'}
                      </p>
                      <div className="vacancy-actions">
                        <a href={item.source_url} target="_blank" rel="noreferrer">
                          Открыть источник
                        </a>
                        <button className="secondary" disabled={matchingBusy} onClick={() => void undislikeVacancy(item.vacancy_id)}>
                          Снять минус
                        </button>
                      </div>
                    </article>
                  ))}
                </div>
              </section>

              {/* Applications section moved to /applications route — slice 2.8.4 */}
            </div>
          </section>
        )}
      </section>
    </main>
  );
}

function Analysis({ data }: { data: Record<string, unknown> }) {
  const hardSkills = asStringArray(data.hard_skills);
  const softSkills = asStringArray(data.soft_skills);
  const tools = asStringArray(data.tools);
  const domains = asStringArray(data.domains);
  const strengths = asStringArray(data.strengths);
  const weaknesses = asStringArray(data.weaknesses);
  const riskFlags = asStringArray(data.risk_flags);
  const recommendations = asStringArray(data.recommendations);
  const matchingKeywords = asStringArray(data.matching_keywords);
  const totalExperience = asNumber(data.total_experience_years);
  const seniorityConfidence = asNumber(data.seniority_confidence);

  return (
    <div className="analysis">
      <div className="profile-card">
        <div>
          <span className="eyebrow">Кандидат</span>
          <h4>{asText(data.candidate_name, 'Имя не определено')}</h4>
          <p>{asText(data.target_role, 'Целевая роль не определена')}</p>
        </div>
        <div>
          <span className="eyebrow">Грейд (оценка модели)</span>
          <h4>{asText(data.seniority, 'Не определен')}</h4>
          <p>{seniorityConfidence === null ? 'Уверенность не рассчитана' : `Уверенность модели: ${Math.round(seniorityConfidence * 100)}%`}</p>
        </div>
        <div>
          <span className="eyebrow">Опыт</span>
          <h4>{totalExperience === null ? 'Не указан' : `${totalExperience} лет`}</h4>
          <p>{asText(data.specialization, 'Специализация не определена')}</p>
        </div>
      </div>

      <div className="analysis-section">
        <h4>Краткий профиль</h4>
        <p>{asText(data.summary, 'Описание пока недоступно')}</p>
      </div>
      <List title="Hard skills" items={hardSkills} />
      <List title="Soft skills" items={softSkills} />
      <List title="Инструменты и технологии" items={tools} />
      <List title="Домены и отрасли" items={domains} />
      <List title="Сильные стороны" items={strengths} />
      <List title="Зоны роста" items={weaknesses} />
      <List title="Риски для найма" items={riskFlags} />
      <List title="Рекомендации" items={recommendations} />
      <List title="Ключевые слова для matching" items={matchingKeywords} />
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="analysis-section">
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}
