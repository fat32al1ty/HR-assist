'use client';

import { FormEvent, Fragment, useEffect, useRef, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
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
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
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
  preferred_work_formats: WorkFormat[];
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
    preferred_work_formats: prefs.preferred_work_format === 'any' ? [] : [prefs.preferred_work_format],
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
  const router = useRouter();
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
  const [appliedVacancies, setAppliedVacancies] = useState<VacancyMatch[]>([]);
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
  const [lastSearchAt, setLastSearchAt] = useState<Date | null>(null);
  const [lastAnalyzedCount, setLastAnalyzedCount] = useState<number | null>(null);
  const [matchesPageSize, setMatchesPageSize] = useState<number>(10);
  const isAdmin = Boolean(user?.is_admin);
  const [dragOver, setDragOver] = useState(false);

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
      const filtered = excludeFeedbackVacancies(current, dislikedVacancies, [...selectedVacancies, ...appliedVacancies], hiddenMatchIds);
      if (filtered.length === current.length) {
        return current;
      }
      return filtered;
    });
  }, [dislikedVacancies, selectedVacancies, appliedVacancies, hiddenMatchIds]);

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

  const visibleMatches = excludeFeedbackVacancies(matches, dislikedVacancies, [...selectedVacancies, ...appliedVacancies], hiddenMatchIds);

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
      setMatchesPageSize(10);
      const metricsInfo = formatMetricsInfo(metrics);
      const headline = formatRecommendationHeadline(visibleMatches.length);
      setMatchingMessage(metricsInfo ? `${headline} ${metricsInfo}` : headline);
      setMatchingProgress(100);
      setMatchingStage('Готово');
      setLastSearchAt(new Date());
      const analyzedCount = typeof metrics.analyzed === 'number' ? metrics.analyzed : null;
      if (analyzedCount !== null) setLastAnalyzedCount(analyzedCount);
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
      preferred_work_format: profileDraft.preferred_work_formats.length === 1 ? profileDraft.preferred_work_formats[0] : 'any',
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

  async function uploadResume(targetFile: File) {
    setBusy(true);
    setMessage('Анализируем резюме…');

    try {
      const formData = new FormData();
      formData.append('file', targetFile);
      const resume = await request<Resume>('/api/resumes', { method: 'POST', body: formData });
      setResumes((current) => [resume, ...current]);
      setFile(null);

      if (resume.status === 'completed') {
        // Already done — redirect immediately to audit page
        router.push(`/audit?resume_id=${resume.id}`);
        return;
      }

      // Resume is still processing — poll until completed then redirect
      setMessage('Анализируем резюме…');
      const MAX_POLL_MS = 120_000;
      const POLL_INTERVAL_MS = 2_000;
      const deadline = Date.now() + MAX_POLL_MS;

      while (Date.now() < deadline) {
        await sleep(POLL_INTERVAL_MS);
        try {
          const list = await request<Resume[]>('/api/resumes');
          const updated = list.find((r) => r.id === resume.id);
          if (!updated) break;
          // Keep local state in sync
          setResumes(list);
          if (updated.status === 'completed') {
            router.push(`/audit?resume_id=${updated.id}`);
            return;
          }
          if (updated.status === 'failed') {
            setMessage(updated.error_message || 'Не удалось обработать резюме');
            break;
          }
        } catch {
          // Poll failure is non-fatal — keep trying until deadline
        }
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Не удалось загрузить резюме');
    } finally {
      setBusy(false);
    }
  }

  function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0] ?? null;
    setFile(picked);
    if (picked) {
      void uploadResume(picked);
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
        setAppliedVacancies((current) => {
          if (current.some((item) => normalizeVacancyId(item.vacancy_id) === vacancyId)) return current;
          return [vacancy, ...current];
        });
        setMatches((current) => removeVacancyMatchEntry(current, vacancy));
        setMatchingMessage(`Отклик создан — вакансия перемещена в раздел «Отклики».`);
      } else if (response.status === 409) {
        const detail = (payload as { detail?: { application_id?: number; message?: string } }).detail;
        const applicationId =
          detail && typeof detail === 'object' && typeof detail.application_id === 'number'
            ? detail.application_id
            : null;
        setAppliedVacancies((current) => {
          if (current.some((item) => normalizeVacancyId(item.vacancy_id) === vacancyId)) return current;
          return [vacancy, ...current];
        });
        setMatches((current) => removeVacancyMatchEntry(current, vacancy));
        setMatchingMessage(
          applicationId
            ? `По этой вакансии уже есть отклик (#${applicationId}).`
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
        {!token ? (
          /* ── Auth screen ──────────────────────────────────────────────── */
          <div className="grid lg:grid-cols-[1.15fr_1fr] gap-10 items-center min-h-[80vh] py-10">
            {/* Hero — left column on desktop, top on mobile */}
            <div className="flex flex-col gap-7 animate-fade-in">
              <div className="inline-flex items-center gap-2.5 w-max">
                <Image
                  src="/brand-preview-assets/aijobmatch-variant2-icon-256.png"
                  alt="AIJobMatch"
                  width={36}
                  height={36}
                  className="rounded-[10px] shadow-[var(--shadow-sm)]"
                />
                <span className="font-[var(--font-display)] font-bold text-[length:var(--text-xl)] tracking-[-0.02em] text-[color:var(--color-ink)]">
                  AIJobMatch
                </span>
              </div>

              <div className="flex flex-col gap-4">
                <span className="inline-flex w-max px-3 py-1 rounded-full border border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[length:var(--text-xs)] font-bold tracking-[0.08em] uppercase text-[color:var(--color-ink-secondary)]">
                  AI-агент по поиску работы
                </span>
                <h1 className="text-[length:var(--text-display)] leading-[var(--leading-tight)] tracking-[-0.035em] font-bold text-[color:var(--color-ink)] max-w-[620px]">
                  AI находит <span className="text-[color:var(--color-accent)]">твои</span> вакансии — и объясняет почему
                </h1>
                <p className="text-[length:var(--text-lg)] leading-[var(--leading-relaxed)] text-[color:var(--color-ink-secondary)] max-w-[560px]">
                  Загружаешь резюме — получаешь отранжированный список вакансий,
                  честный разбор «чего хватает» и «чего нет», и воронку откликов
                  без ручной рутины.
                </p>
              </div>

              <ul className="grid gap-3 max-w-[560px]">
                {[
                  ['Вакансии под вас, а не наоборот', 'AI изучает ваше резюме и подбирает только те предложения, где вы реально подходите — нерелевантный спам не попадает в список.'],
                  ['Честный разбор каждой вакансии', 'Для каждой позиции видно: что у вас уже есть, чего пока не хватает и стоит ли откликаться. Никаких догадок.'],
                  ['Все отклики в одном месте', 'Отправили резюме — отмечаете статус: отправлено, просмотрено, собеседование, оффер. Сопроводительное письмо готовит AI по одной кнопке.'],
                  ['Два карьерных направления', 'Хотите совмещать специалиста и руководителя? Создайте два профиля — каждый получает свои вакансии и историю откликов, ничего не перемешается.'],
                ].map(([title, body]) => (
                  <li key={title} className="flex gap-3">
                    <span className="mt-[3px] inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-subtle)] text-[color:var(--color-accent)] text-[length:var(--text-xs)] font-bold">
                      ✓
                    </span>
                    <div className="flex flex-col gap-0.5">
                      <span className="font-semibold text-[length:var(--text-sm)] text-[color:var(--color-ink)]">
                        {title}
                      </span>
                      <span className="text-[length:var(--text-sm)] leading-[var(--leading-snug)] text-[color:var(--color-ink-secondary)]">
                        {body}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </div>

            {/* Auth card — right column on desktop */}
            <Card className="w-full max-w-md lg:justify-self-end animate-fade-in">
              <CardHeader>
                <CardTitle>
                  {authFormMode === 'login'
                    ? 'Вход в кабинет'
                    : authFormMode === 'register'
                      ? 'Регистрация'
                      : 'Восстановление пароля'}
                </CardTitle>
                <CardDescription>
                  {authFormMode === 'login'
                    ? 'Войдите, чтобы начать подбор вакансий'
                    : authFormMode === 'register'
                      ? 'Создайте аккаунт — нужен ключ бета-тестера'
                      : 'Введите новый пароль и ключ бета-тестера'}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form className="flex flex-col gap-3" onSubmit={handleAuth}>
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
                  <Button type="submit" variant="primary" size="lg" disabled={busy} className="w-full mt-1">
                    {authFormMode === 'login'
                      ? 'Войти'
                      : authFormMode === 'register'
                        ? 'Зарегистрироваться'
                        : 'Сбросить пароль'}
                  </Button>
                  {authFormMode === 'login' ? (
                    <div className="flex flex-col gap-2">
                      <Button
                        variant="secondary"
                        type="button"
                        className="w-full"
                        onClick={() => {
                          setAuthFormMode('register');
                          setMessage('');
                        }}
                      >
                        Нет аккаунта? Зарегистрироваться
                      </Button>
                      <Button
                        variant="ghost"
                        type="button"
                        className="w-full"
                        onClick={() => {
                          setAuthFormMode('reset');
                          setMessage('');
                        }}
                      >
                        Забыли пароль?
                      </Button>
                    </div>
                  ) : (
                    <Button
                      variant="secondary"
                      type="button"
                      className="w-full"
                      onClick={() => {
                        setAuthFormMode('login');
                        setMessage('');
                      }}
                    >
                      Назад ко входу
                    </Button>
                  )}
                </form>
                {message ? (
                  <p className="mt-3 rounded-[var(--radius-md)] px-3 py-2 bg-[var(--color-warning-subtle)] text-[color:var(--color-warning)] border border-[color-mix(in_srgb,var(--color-warning)_25%,transparent)] text-[length:var(--text-sm)]">
                    {message}
                  </p>
                ) : null}
              </CardContent>
            </Card>
          </div>
        ) : (
          /* ── Logged-in workspace ──────────────────────────────────────── */
          <div className="workspace stagger-children">
            {/* ── Sidebar ─────────────────────────────────────────────── */}
            <aside className="flex flex-col gap-3.5 animate-fade-in">
              {/* Upload card */}
              <Card className="border-transparent shadow-none">
                <CardHeader className="pb-3">
                  <CardTitle className="text-[length:var(--text-2xl)]">Резюме</CardTitle>
                  <CardDescription>
                    PDF или DOCX · до {RESUME_LIMIT} профилей
                  </CardDescription>
                </CardHeader>
                <CardContent className="flex flex-col gap-3">
                  {/* Drop zone */}
                  <label
                    className={[
                      'flex flex-col items-center justify-center gap-2 rounded-[var(--radius-lg)] border-2 border-dashed',
                      'px-4 py-6 cursor-pointer transition-colors duration-[var(--duration-fast)]',
                      dragOver
                        ? 'border-[var(--color-accent)] bg-[var(--color-accent-subtle)]'
                        : 'border-[color-mix(in_srgb,var(--color-accent)_45%,transparent)] hover:border-[var(--color-accent)] hover:bg-[var(--color-accent-subtle)]',
                      (busy || resumes.length >= RESUME_LIMIT) ? 'opacity-50 pointer-events-none' : '',
                    ].join(' ')}
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setDragOver(false);
                      const f = e.dataTransfer.files[0];
                      if (f) void uploadResume(f);
                    }}
                  >
                    <svg className="w-8 h-8 text-[color:var(--color-ink-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                    </svg>
                    <div className="text-center select-none">
                      <span className="block text-[color:var(--color-ink)] text-[length:var(--text-sm)] font-semibold">
                        {busy ? 'Анализируем резюме…' : dragOver ? 'Отпустите файл' : 'Загрузите резюме'}
                      </span>
                      {!busy && !dragOver ? (
                        <span className="block text-[color:var(--color-ink-muted)] text-[length:var(--text-xs)] mt-0.5">PDF или DOCX · перетащите или нажмите</span>
                      ) : null}
                    </div>
                    <input
                      type="file"
                      className="sr-only"
                      accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      disabled={busy || resumes.length >= RESUME_LIMIT}
                      onChange={handleFileChange}
                    />
                  </label>
                  {message ? (
                    <p className="rounded-[var(--radius-md)] px-3 py-2 bg-[var(--color-warning-subtle)] text-[color:var(--color-warning)] border border-[color-mix(in_srgb,var(--color-warning)_25%,transparent)] text-[length:var(--text-sm)]">
                      {message}
                    </p>
                  ) : null}
                </CardContent>
              </Card>

              {/* ── Что ищу section ─────────────────────────────────── */}
              {profileDraft ? (
                <Card className="animate-fade-in border-transparent shadow-none">
                  <CardHeader className="pb-3">
                    <CardTitle>Что ищу</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-4 min-w-0">
                    <div className="grid gap-1.5 text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
                      <span>Формат работы <em className="font-normal not-italic text-[color:var(--color-ink-muted)]">(любой если не выбрано)</em></span>
                      <div className="radio-row">
                        {WORK_FORMAT_OPTIONS.filter((o) => o.value !== 'any').map((option) => (
                          <label key={option.value} className="radio-chip">
                            <input
                              type="checkbox"
                              value={option.value}
                              checked={profileDraft.preferred_work_formats.includes(option.value)}
                              onChange={(e) => {
                                const next = e.target.checked
                                  ? [...profileDraft.preferred_work_formats, option.value]
                                  : profileDraft.preferred_work_formats.filter((v) => v !== option.value);
                                updateProfileDraft({ preferred_work_formats: next });
                              }}
                            />
                            <span>{option.label}</span>
                          </label>
                        ))}
                      </div>
                    </div>

                    <div className="grid gap-1.5 text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
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
                      <label className="grid gap-1.5 text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
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

                    <label className="grid gap-1.5 text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
                      <span>Желаемые должности <em className="font-normal not-italic text-[color:var(--color-ink-muted)]">(до 10)</em></span>
                      <textarea
                        key={profileDraft.preferred_titles.join(',')}
                        rows={2}
                        defaultValue={profileDraft.preferred_titles.join(', ')}
                        onBlur={(event) => {
                          const parts = event.target.value
                            .split(',')
                            .map((s) => s.trim())
                            .filter(Boolean)
                            .slice(0, 10);
                          updateProfileDraft({ preferred_titles: parts });
                        }}
                        placeholder="Backend Engineer, Python Developer"
                        className="w-full font-normal"
                      />
                    </label>

                    <div className="grid gap-1.5 text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
                      <span>Зарплата, ₽/мес.</span>
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
                          className="font-normal"
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
                          className="font-normal"
                        />
                      </div>
                    </div>

                    {curatedSkills.length > 0 ? (
                      <Collapsible>
                        <CollapsibleTrigger className="group flex items-center justify-between w-full text-left px-0 py-2 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">
                          <span>Ручная курация скиллов</span>
                          <span className="flex items-center gap-2">
                            <span className="text-[length:var(--text-xs)] bg-[var(--color-surface-muted)] px-2 py-0.5 rounded-full">
                              {curatedSkills.length}
                            </span>
                            <span className="transition-transform duration-[var(--duration-fast)] group-data-[state=open]:rotate-180">▼</span>
                          </span>
                        </CollapsibleTrigger>
                        <CollapsibleContent className="data-[state=open]:animate-slide-down">
                          <div className="curated-block mt-2">
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
                        </CollapsibleContent>
                      </Collapsible>
                    ) : null}
                  </CardContent>
                </Card>
              ) : null}

              {/* Funnel card */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="text-[length:var(--text-2xl)]">Моя воронка</CardTitle>
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
                          <span className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">Проанализировано</span>
                          <span className="text-[length:var(--text-sm)] font-semibold font-[var(--font-mono)] text-[color:var(--color-ink)]">
                            {funnel ? funnel.analyzed_count : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between items-baseline">
                          <span className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">Отобрано</span>
                          <span className="text-[length:var(--text-sm)] font-semibold font-[var(--font-mono)] text-[color:var(--color-ink)]">
                            {funnel && (funnel.selected_count > 0 || funnel.matched_count > 0)
                              ? `${funnel.selected_count} / ${funnel.matched_count}`
                              : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between items-baseline">
                          <span className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">Последний поиск</span>
                          <span className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
                            {funnel ? formatRelativeTimeRu(funnel.last_search_at) : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between items-baseline">
                          <span className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">Следующее обновление</span>
                          <span className="text-[length:var(--text-sm)] font-semibold font-[var(--font-mono)] text-[color:var(--color-ink)]">
                            {warmupStatus?.running ? 'идёт сейчас' : showCountdown ? formatCountdown(nextEtaMs as number) : '—'}
                          </span>
                        </div>
                        {visibleMatches.length > 0 ? (
                          <div className="flex justify-between items-baseline">
                            <span className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">Вакансий найдено</span>
                            <span className="text-[length:var(--text-sm)] font-semibold font-[var(--font-mono)] text-[color:var(--color-ink)]">{visibleMatches.length}</span>
                          </div>
                        ) : null}
                        <div className="flex justify-between items-baseline">
                          <span className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">Поиск вакансий</span>
                          <span className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
                            {warmupStatus?.running ? 'идёт сейчас' : warmupStatus?.enabled ? 'активен' : 'выключен'}
                          </span>
                        </div>
                      </>
                    );
                  })()}
                </CardContent>
              </Card>
            </aside>

            {/* ── Main column ─────────────────────────────────────────── */}
            <div className="workspace-main">
              {/* ── Резюме section ──────────────────────────────────── */}
              <Card className="animate-fade-in border-transparent shadow-none">
                <CardHeader className="pb-3">
                  <CardTitle>Моё резюме</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  {resumes.length === 0 ? (
                    <div className="flex flex-col items-center text-center gap-3 py-8">
                      <svg className="w-12 h-12 text-[color:var(--color-ink-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                      </svg>
                      <div>
                        <p className="text-[color:var(--color-ink)] text-[length:var(--text-sm)] font-semibold">Загрузите резюме, чтобы начать</p>
                        <p className="text-[color:var(--color-ink-secondary)] text-[length:var(--text-xs)] mt-1">AI проанализирует его и подберёт подходящие вакансии</p>
                      </div>
                    </div>
                  ) : null}
                  {resumes.map((resume) => (
                    <article
                      key={resume.id}
                      className={[
                        'grid gap-2 border rounded-[var(--radius-xl)] p-4 bg-[var(--color-surface)]',
                        resume.is_active
                          ? 'border-[var(--color-accent)] shadow-[0_0_0_2px_color-mix(in_srgb,var(--color-accent)_18%,transparent)]'
                          : 'border-[var(--color-border)] shadow-[var(--shadow-xs)]',
                      ].join(' ')}
                    >
                      <div className="flex justify-between gap-3 items-start">
                        <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                          <h3 className="text-[length:var(--text-xl)] font-[var(--font-display)] font-semibold leading-[var(--leading-tight)] tracking-[-0.03em] break-words">
                            {resume.analysis
                              ? (asText(resume.analysis.target_role, '') || resume.original_filename)
                              : resume.original_filename}
                            {resume.is_active ? (
                              <span className="resume-active-tag ml-2">активный</span>
                            ) : null}
                          </h3>
                          <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] break-words">{resume.original_filename}</span>
                          {resume.status === 'failed' || resume.status === 'processing' ? (
                            <span className={`status ${resume.status}`}>
                              {statusLabels[resume.status]}
                            </span>
                          ) : null}
                        </div>
                        <div className="inline-flex gap-2 items-center justify-end shrink-0">
                          {!resume.is_active ? (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void activateResumeProfile(resume.id)}
                              className="text-[length:var(--text-xs)] font-medium text-[color:var(--color-accent)] hover:opacity-70 transition-opacity disabled:opacity-40"
                            >
                              Сделать активным
                            </button>
                          ) : null}
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => {
                              if (window.confirm('Удалить резюме? Это действие нельзя отменить.')) {
                                void deleteResume(resume.id);
                              }
                            }}
                            className="w-7 h-7 flex items-center justify-center rounded-full text-[color:var(--color-ink-muted)] hover:text-[color:var(--color-danger)] hover:bg-[var(--color-danger-subtle)] transition-colors disabled:opacity-40"
                            title="Удалить резюме"
                          >
                            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                              <path d="M2 2l10 10M12 2L2 12"/>
                            </svg>
                          </button>
                        </div>
                      </div>
                      {resume.error_message ? (
                        <p className="rounded-[var(--radius-md)] px-3 py-2 bg-[var(--color-warning-subtle)] text-[color:var(--color-warning)] border border-[color-mix(in_srgb,var(--color-warning)_25%,transparent)] text-[length:var(--text-sm)]">
                          {resume.error_message}
                        </p>
                      ) : null}
                      {resume.analysis ? (
                        <Analysis
                          data={resume.analysis}
                          expectedSalaryMin={userPrefs?.expected_salary_min}
                          expectedSalaryMax={userPrefs?.expected_salary_max}
                        />
                      ) : null}
                      {resume.status === 'completed' ? (
                        <Button
                          variant="primary"
                          size="md"
                          onClick={() => router.push(`/audit?resume_id=${resume.id}`)}
                          className="w-full mt-1"
                        >
                          Открыть аудит резюме →
                        </Button>
                      ) : null}
                    </article>
                  ))}
                </CardContent>
              </Card>

              {/* ── Подбор вакансий section ─────────────────────────── */}
              <Card className="animate-fade-in border-transparent shadow-none">
                <CardHeader className="pb-3">
                  <CardTitle>Подбор вакансий</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-[var(--radius-xl)] border border-[color-mix(in_srgb,var(--color-accent)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-accent)_6%,transparent)] px-4 py-3">
                    <div>
                      <p className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
                        {matchingBusy ? 'Ищем подходящие вакансии…' : 'Подобрать вакансии'}
                      </p>
                      <p className="text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]">
                        {matchingBusy ? 'Это займёт несколько минут' : 'AI подберёт вакансии под ваш профиль'}
                      </p>
                    </div>
                    <Button
                      variant="primary"
                      size="lg"
                      className="px-6 shrink-0 sm:self-auto self-stretch"
                      onClick={() => profileDraft ? void saveProfileAndRecommend() : void refreshVacancyIndex()}
                      disabled={matchingBusy || !selectedResumeId}
                    >
                      {profileSaving ? 'Сохраняем…' : matchingBusy ? 'Ищем…' : 'Подобрать'}
                    </Button>
                  </div>
                  {matchingBusy ? (
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
                          <Button
                            variant="danger"
                            size="sm"
                            disabled={cancelRequested}
                            onClick={() => void cancelRecommendationJob()}
                          >
                            {cancelRequested ? 'Останавливаем...' : 'Отменить'}
                          </Button>
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {(matchingMessage || (visibleMatches.length > 0 && lastSearchAt)) ? (
                    <div className="rounded-[var(--radius-xl)] border border-[color-mix(in_srgb,var(--color-accent)_30%,transparent)] bg-[color-mix(in_srgb,var(--color-accent)_6%,transparent)] px-4 py-3 flex flex-col gap-1">
                      {matchingMessage ? (
                        <p className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">{matchingMessage}</p>
                      ) : null}
                      {visibleMatches.length > 0 && lastSearchAt ? (
                        <p className="text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]">
                          {`Показано ${Math.min(matchesPageSize, visibleMatches.length)} из ${visibleMatches.length}${lastAnalyzedCount ? ` · проверено ${lastAnalyzedCount} новых` : ''} · запуск в ${lastSearchAt.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}`}
                        </p>
                      ) : null}
                    </div>
                  ) : null}

                  {/* Match cards */}
                  <div className="flex flex-col gap-3">
                    {visibleMatches.length === 0 ? (
                      <p className="text-[color:var(--color-ink-secondary)] text-[length:var(--text-sm)] italic">
                        После запуска здесь появятся подходящие вакансии.
                      </p>
                    ) : null}
                    {visibleMatches.slice(0, matchesPageSize).map((match, matchIndex) => {
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
                          {/* Match card using token classes */}
                          <article
                            className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-lg)] p-4 flex flex-col gap-3 shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)] transition-shadow duration-[var(--duration-fast)]"
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
                            {/* Card header row */}
                            <div className="flex items-start justify-between gap-3">
                              <h3 className="min-w-0 text-[length:var(--text-xl)] font-[var(--font-display)] font-semibold leading-[var(--leading-tight)] tracking-[-0.025em] text-[color:var(--color-ink)]">
                                {match.title}
                              </h3>
                              {/* Relevance + salary right-aligned, mono */}
                              <div className="flex flex-col items-end gap-0.5 shrink-0 font-[var(--font-mono)] text-[length:var(--text-sm)]">
                                <span className="font-semibold text-[color:var(--color-ink)]">
                                  {scoreToPercent(match.similarity_score)}
                                </span>
                                <span className="text-[length:var(--text-xs)] font-sans font-normal text-[color:var(--color-ink-muted)]">релевантность</span>
                                {(() => {
                                  const badge = renderSalaryBadge(match);
                                  if (!badge) return null;
                                  const fitColor =
                                    badge.fit === 'below'
                                      ? 'text-[color:var(--color-warning)]'
                                      : badge.fit === 'above'
                                        ? 'text-[color:var(--color-success)]'
                                        : 'text-[color:var(--color-ink-secondary)]';
                                  return (
                                    <span className={fitColor}>
                                      {badge.text}
                                    </span>
                                  );
                                })()}
                              </div>
                            </div>

                            {/* Meta */}
                            <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] m-0">
                              {match.company || 'Компания не указана'}
                              {' · '}
                              {match.location || 'Локация не указана'}
                            </p>

                            {/* Почему показали */}
                            {reasonFromMatch(match) ? (
                              <Collapsible>
                                <CollapsibleTrigger className="group flex items-center justify-end w-full text-right text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] hover:text-[color:var(--color-ink-secondary)] transition-colors py-0.5 gap-1">
                                  <span>Почему показали</span>
                                  <span className="transition-transform duration-[var(--duration-fast)] group-data-[state=open]:rotate-180">▼</span>
                                </CollapsibleTrigger>
                                <CollapsibleContent className="data-[state=open]:animate-slide-down">
                                  <p className="match-reason text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-snug)] mt-1">
                                    {reasonFromMatch(match)}
                                  </p>
                                </CollapsibleContent>
                              </Collapsible>
                            ) : null}

                            {/* Fit grid — pill badges */}
                            <div className="fit-grid">
                              <div className="fit-box fit-matched">
                                <p className="fit-title">Подходишь</p>
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
                                  <p className="fit-empty">совпадение по ключевым словам</p>
                                )}
                              </div>
                              <div className="fit-box fit-missing">
                                <p className="fit-title">Не хватает</p>
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
                                  <p className="fit-empty">все требования закрыты</p>
                                )}
                              </div>
                            </div>

                            {/* Actions */}
                            <div className="flex items-center gap-2 flex-wrap pt-1">
                              <Button
                                variant="primary"
                                size="sm"
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
                              </Button>
                              <button
                                type="button"
                                disabled={matchingBusy}
                                title="Интересно"
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
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[var(--radius-md)] text-[length:var(--text-xs)] font-medium border border-transparent text-[color:var(--color-ink-muted)] hover:text-[color:var(--color-accent)] hover:bg-[color-mix(in_srgb,var(--color-accent)_10%,transparent)] hover:border-[color-mix(in_srgb,var(--color-accent)_30%,transparent)] transition-colors disabled:opacity-40"
                              >
                                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 1v10M1 6h10"/></svg>
                                Интересно
                              </button>
                              <button
                                type="button"
                                disabled={matchingBusy}
                                title="Не подходит"
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
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-[var(--radius-md)] text-[length:var(--text-xs)] font-medium border border-transparent text-[color:var(--color-ink-muted)] hover:text-[color:var(--color-danger)] hover:bg-[var(--color-danger-subtle)] hover:border-[color-mix(in_srgb,var(--color-danger)_30%,transparent)] transition-colors disabled:opacity-40"
                              >
                                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M1 6h10"/></svg>
                                Не подходит
                              </button>
                              <a
                                href={match.source_url}
                                target="_blank"
                                rel="noreferrer"
                                className="ml-auto text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] hover:text-[color:var(--color-accent)] transition-colors no-underline font-semibold"
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
                                Источник →
                              </a>
                            </div>
                          </article>
                        </Fragment>
                      );
                    })}
                  </div>
                  {visibleMatches.length > matchesPageSize ? (
                    <Button
                      variant="secondary"
                      type="button"
                      className="w-full"
                      onClick={() => setMatchesPageSize((prev) => Math.min(prev + 10, visibleMatches.length))}
                    >
                      Показать ещё 10
                    </Button>
                  ) : null}
                </CardContent>
              </Card>

              {/* ── Отклики ─────────────────────────────────────────── */}
              <Card className="animate-fade-in border-transparent shadow-none">
                <Collapsible>
                  <CardHeader className="pb-3">
                    <CollapsibleTrigger className="group flex items-center justify-between w-full text-left gap-3">
                      <CardTitle>Отклики</CardTitle>
                      <span className="flex items-center gap-2 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                        <span className="text-[length:var(--text-xs)] bg-[var(--color-surface-muted)] px-2 py-0.5 rounded-full">
                          {appliedVacancies.length}
                        </span>
                        <span className="transition-transform duration-[var(--duration-fast)] group-data-[state=open]:rotate-180">▼</span>
                      </span>
                    </CollapsibleTrigger>
                  </CardHeader>
                  <CollapsibleContent className="data-[state=open]:animate-slide-down">
                    <CardContent className="pt-0 flex flex-col gap-3">
                      {appliedVacancies.length === 0 ? (
                        <p className="text-[color:var(--color-ink-secondary)] text-[length:var(--text-sm)] italic">
                          Нажмите «Откликнуться» на карточке вакансии — она переместится сюда.
                        </p>
                      ) : null}
                      {appliedVacancies.map((item) => (
                        <article
                          key={`applied-${item.vacancy_id}`}
                          className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-lg)] p-4 flex flex-col gap-2 shadow-[var(--shadow-xs)]"
                        >
                          <h3 className="text-[length:var(--text-lg)] font-[var(--font-display)] font-semibold leading-[var(--leading-tight)] tracking-[-0.02em]">
                            {item.title}
                          </h3>
                          <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] m-0">
                            {item.company || 'Компания не указана'}{item.location ? ` · ${item.location}` : ''}
                          </p>
                          {item.source_url ? (
                            <a
                              href={item.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-accent)] hover:opacity-75 transition-opacity no-underline self-start"
                            >
                              Открыть вакансию ↗
                            </a>
                          ) : null}
                        </article>
                      ))}
                    </CardContent>
                  </CollapsibleContent>
                </Collapsible>
              </Card>

              {/* ── Collapsible archived sections ──────────────────── */}
              <Card className="animate-fade-in border-transparent shadow-none">
                <Collapsible>
                  <CardHeader className="pb-3">
                    <CollapsibleTrigger className="group flex items-center justify-between w-full text-left gap-3">
                      <CardTitle>Отобранные вакансии</CardTitle>
                      <span className="flex items-center gap-2 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                        <span className="text-[length:var(--text-xs)] bg-[var(--color-surface-muted)] px-2 py-0.5 rounded-full">
                          {selectedVacancies.length}
                        </span>
                        <span className="transition-transform duration-[var(--duration-fast)] group-data-[state=open]:rotate-180">▼</span>
                      </span>
                    </CollapsibleTrigger>
                  </CardHeader>
                  <CollapsibleContent className="data-[state=open]:animate-slide-down">
                    <CardContent className="pt-0 flex flex-col gap-3">
                      {selectedVacancies.length === 0 ? (
                        <p className="text-[color:var(--color-ink-secondary)] text-[length:var(--text-sm)] italic">
                          Пока нет отобранных. Нажмите «+ Плюс» в подборке.
                        </p>
                      ) : null}
                      {selectedVacancies.map((item) => (
                        <article
                          key={`selected-${item.vacancy_id}`}
                          className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-lg)] p-4 flex flex-col gap-2 shadow-[var(--shadow-xs)]"
                        >
                          <h3 className="text-[length:var(--text-lg)] font-[var(--font-display)] font-semibold leading-[var(--leading-tight)] tracking-[-0.02em]">
                            {item.title}
                          </h3>
                          <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] m-0">
                            {item.company || 'Компания не указана'} · {item.location || 'Локация не указана'}
                          </p>
                          <div className="flex items-center gap-2 flex-wrap">
                            <a
                              href={item.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-accent)] hover:text-[color:var(--color-accent-hover)] transition-colors no-underline"
                            >
                              Источник →
                            </a>
                            <Button
                              variant="secondary"
                              size="sm"
                              disabled={matchingBusy}
                              onClick={() => void unlikeVacancy(item.vacancy_id)}
                            >
                              Убрать
                            </Button>
                          </div>
                        </article>
                      ))}
                    </CardContent>
                  </CollapsibleContent>
                </Collapsible>
              </Card>

              <Card className="animate-fade-in border-transparent shadow-none">
                <Collapsible>
                  <CardHeader className="pb-3">
                    <CollapsibleTrigger className="group flex items-center justify-between w-full text-left gap-3">
                      <CardTitle>Отклонённые вакансии</CardTitle>
                      <span className="flex items-center gap-2 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                        <span className="text-[length:var(--text-xs)] bg-[var(--color-surface-muted)] px-2 py-0.5 rounded-full">
                          {dislikedVacancies.length}
                        </span>
                        <span className="transition-transform duration-[var(--duration-fast)] group-data-[state=open]:rotate-180">▼</span>
                      </span>
                    </CollapsibleTrigger>
                  </CardHeader>
                  <CollapsibleContent className="data-[state=open]:animate-slide-down">
                    <CardContent className="pt-0 flex flex-col gap-3">
                      {dislikedVacancies.length === 0 ? (
                        <p className="text-[color:var(--color-ink-secondary)] text-[length:var(--text-sm)] italic">
                          Пока нет минусованных вакансий.
                        </p>
                      ) : null}
                      {dislikedVacancies.map((item) => (
                        <article
                          key={`disliked-${item.vacancy_id}`}
                          className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-lg)] p-4 flex flex-col gap-2 shadow-[var(--shadow-xs)]"
                        >
                          <h3 className="text-[length:var(--text-lg)] font-[var(--font-display)] font-semibold leading-[var(--leading-tight)] tracking-[-0.02em]">
                            {item.title}
                          </h3>
                          <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] m-0">
                            {item.company || 'Компания не указана'} · {item.location || 'Локация не указана'}
                          </p>
                          <div className="flex items-center gap-2 flex-wrap">
                            <a
                              href={item.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-accent)] hover:text-[color:var(--color-accent-hover)] transition-colors no-underline"
                            >
                              Источник →
                            </a>
                            <Button
                              variant="secondary"
                              size="sm"
                              disabled={matchingBusy}
                              onClick={() => void undislikeVacancy(item.vacancy_id)}
                            >
                              Снять минус
                            </Button>
                          </div>
                        </article>
                      ))}
                    </CardContent>
                  </CollapsibleContent>
                </Collapsible>
              </Card>

              {/* Applications section moved to /applications route — slice 2.8.4 */}
            </div>
          </div>
        )}
      </section>

      {/* ── Footer ───────────────────────────────────────────────────────── */}
      <footer className="w-full mt-auto border-t border-[var(--color-border)] bg-[#f3f6fb]/80 backdrop-blur-sm">
        <div className="max-w-[1180px] mx-auto px-6 py-6">

          {/* Top row: brand + nav */}
          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-6 mb-6">

            {/* Brand */}
            <div className="flex flex-col gap-2 max-w-[260px]">
              <div className="flex items-center gap-2">
                <Image src="/brand-preview-assets/aijobmatch-variant2-icon-256.png" alt="AIJobMatch" width={24} height={24} className="rounded-[6px] shadow-[var(--shadow-sm)]" />
                <span className="font-bold text-[length:var(--text-sm)] tracking-[-0.02em] text-[color:var(--color-ink)]">AIJobMatch</span>
              </div>
              <p className="text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
                AI-ассистент для соискателей — умный подбор вакансий и воронка откликов.
              </p>
            </div>

            {/* Nav columns */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 sm:gap-6 text-[length:var(--text-xs)]">
              <div className="flex flex-col gap-1.5">
                <span className="font-semibold text-[color:var(--color-ink)] mb-0.5">Продукт</span>
                <a href="/vacancies" className="text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">Подбор вакансий</a>
                <a href="/resume-analysis" className="text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">Анализ резюме</a>
                <a href="/funnel" className="text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">Воронка откликов</a>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="font-semibold text-[color:var(--color-ink)] mb-0.5">Компания</span>
                <a href="/about" className="text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">О проекте</a>
                <a href="/contacts" className="text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">Контакты</a>
                <a href="https://github.com/fat32al1ty/HR-assist" target="_blank" rel="noreferrer" className="text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">GitHub</a>
              </div>
              <div className="flex flex-col gap-1.5">
                <span className="font-semibold text-[color:var(--color-ink)] mb-0.5">Правовое</span>
                <a href="/privacy" className="text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">Конфиден­циальность</a>
                <a href="/terms" className="text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">Условия</a>
                <a href="/cookies" className="text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">Cookies</a>
              </div>
            </div>
          </div>

          {/* Tech stack */}
          <div className="mb-4">
            <p className="text-[length:var(--text-xs)] font-semibold tracking-[0.08em] uppercase text-[color:var(--color-ink-muted)] mb-2.5">Стек</p>
            <div className="flex flex-wrap gap-2">
              {[
                { name: "Next.js",     color: "#000000", icon: (
                  <svg viewBox="0 0 180 180" fill="none" className="w-5 h-5 shrink-0"><mask id="nxt-m" style={{maskType:"alpha"}} maskUnits="userSpaceOnUse" x="0" y="0" width="180" height="180"><circle cx="90" cy="90" r="90" fill="black"/></mask><g mask="url(#nxt-m)"><circle cx="90" cy="90" r="90" fill="black"/><path d="M149.508 157.52L69.142 54H54V125.97H66.1V69.438L139.999 164.845C143.333 162.614 146.509 160.165 149.508 157.52Z" fill="url(#nxt-g1)"/><rect x="115" y="54" width="12" height="72" fill="url(#nxt-g2)"/></g><defs><linearGradient id="nxt-g1" x1="109" y1="116.5" x2="144.5" y2="160.5" gradientUnits="userSpaceOnUse"><stop stopColor="white"/><stop offset="1" stopColor="white" stopOpacity="0"/></linearGradient><linearGradient id="nxt-g2" x1="121" y1="54" x2="120.799" y2="106.875" gradientUnits="userSpaceOnUse"><stop stopColor="white"/><stop offset="1" stopColor="white" stopOpacity="0"/></linearGradient></defs></svg>
                )},
                { name: "TypeScript",  color: "#3178C6", icon: (
                  <svg viewBox="0 0 256 256" className="w-5 h-5 shrink-0"><rect width="256" height="256" fill="#3178C6" rx="16"/><path fill="white" d="M150.5 200.5v-27.4c4.5 2.3 9.6 4 14.8 5 5.2 1 10.5 1.5 15.7 1.5 3.2 0 6.3-.3 9.3-.8 3-.5 5.7-1.4 8-2.7 2.3-1.3 4.1-3 5.5-5.2 1.4-2.2 2-4.9 2-8.2 0-2.5-.5-4.7-1.6-6.6-1-1.9-2.5-3.6-4.4-5.1-1.9-1.5-4.1-2.9-6.7-4.2-2.6-1.3-5.4-2.7-8.4-4.1-3.5-1.6-6.7-3.3-9.7-5.1-3-1.8-5.6-3.8-7.8-6.1-2.2-2.3-3.9-4.9-5.2-7.9-1.3-3-1.9-6.5-1.9-10.5 0-5.4 1.1-10 3.3-13.7 2.2-3.7 5.1-6.8 8.7-9.2 3.6-2.4 7.7-4.1 12.3-5.2 4.6-1.1 9.4-1.7 14.4-1.7 4.3 0 8.4.3 12.2.8 3.8.5 7.3 1.3 10.4 2.3v26.6c-1.8-1.1-3.8-2-5.9-2.7-2.1-.7-4.3-1.3-6.5-1.7-2.2-.4-4.4-.7-6.6-.9-2.2-.2-4.3-.3-6.2-.3-3 0-5.9.3-8.5.9-2.6.6-4.9 1.5-6.8 2.8-1.9 1.3-3.4 2.9-4.5 4.9-1.1 2-1.6 4.3-1.6 7 0 2.3.5 4.3 1.4 5.9.9 1.6 2.3 3.1 4 4.4 1.7 1.3 3.8 2.5 6.2 3.7 2.4 1.2 5.1 2.5 8.2 3.9 3.7 1.7 7.2 3.5 10.3 5.4 3.1 1.9 5.9 4 8.2 6.4 2.3 2.4 4.1 5.2 5.4 8.3 1.3 3.1 2 6.8 2 11.1 0 5.8-1.1 10.7-3.3 14.5-2.2 3.8-5.2 6.9-9 9.2-3.8 2.3-8.1 4-13.1 5-5 1-10.2 1.5-15.7 1.5-5.3 0-10.5-.5-15.7-1.4-5.2-.9-9.9-2.3-14.1-4.1ZM92.6 110.7H128v-27H27v27h35.2V214h30.4V110.7Z"/></svg>
                )},
                { name: "FastAPI",     color: "#009688", icon: (
                  <svg viewBox="0 0 256 256" className="w-5 h-5 shrink-0"><circle cx="128" cy="128" r="128" fill="#009688"/><path fill="white" d="M140 32 76 144h60l-20 80 88-120h-64z"/></svg>
                )},
                { name: "Python",      color: "#3776AB", icon: (
                  <svg viewBox="0 0 256 255" className="w-5 h-5 shrink-0"><path fill="#3776AB" d="M126.9 0C62.4 0 66.3 27.5 66.3 27.5l.1 28.5h61.7v8.5H41.8S0 59.7 0 124.9c0 65.2 36.1 62.9 36.1 62.9h21.6v-30.3s-1.2-36 35.4-36h61.1s34.3.6 34.3-33.2V33.8C188.5 1.3 152.1 0 126.9 0Zm-34 19.6c6.1 0 11 4.9 11 11s-4.9 11-11 11-11-4.9-11-11 4.9-11 11-11Z"/><path fill="#FFD43B" d="M129.1 254.6c64.5 0 60.6-27.5 60.6-27.5l-.1-28.5h-61.7v-8.5h86.3s41.8 4.8 41.8-60.5c0-65.2-36.1-62.9-36.1-62.9h-21.6v30.3s1.2 36-35.4 36h-61s-34.3-.6-34.3 33.2v55.4c0 32.5 36.4 33.8 61.5 33.8Zm34-19.6c-6.1 0-11-4.9-11-11s4.9-11 11-11 11 4.9 11 11-4.9 11-11 11Z"/></svg>
                )},
                { name: "PostgreSQL",  color: "#336791", icon: (
                  <svg viewBox="0 0 256 256" className="w-5 h-5 shrink-0"><ellipse cx="128" cy="100" rx="100" ry="72" fill="#336791"/><rect x="28" y="100" width="200" height="72" fill="#336791"/><ellipse cx="128" cy="172" rx="100" ry="28" fill="#336791"/><ellipse cx="128" cy="100" rx="100" ry="28" fill="#5b9bd5"/><path d="M228 100v72c0 15-45 28-100 28S28 187 28 172v-72" fill="none" stroke="#fff" strokeWidth="4" opacity=".3"/><text x="128" y="116" textAnchor="middle" fill="white" fontSize="52" fontWeight="bold" fontFamily="serif">pg</text></svg>
                )},
                { name: "OpenAI",      color: "#10A37F", icon: (
                  <svg viewBox="0 0 41 41" fill="currentColor" className="w-5 h-5 shrink-0" style={{color:"#10A37F"}}><path d="M37.532 16.87a9.963 9.963 0 0 0-.856-8.184 10.078 10.078 0 0 0-10.855-4.835 9.964 9.964 0 0 0-6.75-3.014 10.079 10.079 0 0 0-9.617 6.977 9.967 9.967 0 0 0-6.63 4.811 10.079 10.079 0 0 0 1.24 11.817 9.965 9.965 0 0 0 .856 8.185 10.079 10.079 0 0 0 10.855 4.835 9.965 9.965 0 0 0 6.75 3.014 10.078 10.078 0 0 0 9.617-6.976 9.967 9.967 0 0 0 6.63-4.812 10.079 10.079 0 0 0-1.24-11.817zm-14.97 20.415a7.477 7.477 0 0 1-4.793-1.727c.061-.033.168-.091.237-.134l7.964-4.6a1.294 1.294 0 0 0 .655-1.134V19.054l3.366 1.944a.12.12 0 0 1 .066.092v9.299a7.505 7.505 0 0 1-7.495 7.496zM6.392 33.006a7.471 7.471 0 0 1-.894-5.023c.06.036.162.099.237.141l7.964 4.6a1.297 1.297 0 0 0 1.308 0l9.724-5.614v3.888a.12.12 0 0 1-.048.103l-8.051 4.649a7.504 7.504 0 0 1-10.24-2.744zM4.297 13.62A7.469 7.469 0 0 1 8.2 10.333c0 .068-.004.19-.004.274v9.201a1.294 1.294 0 0 0 .654 1.132l9.723 5.614-3.366 1.944a.12.12 0 0 1-.114.012L7.044 23.86a7.504 7.504 0 0 1-2.747-10.24zm27.658 6.437l-9.724-5.615 3.367-1.943a.121.121 0 0 1 .114-.012l8.048 4.648a7.498 7.498 0 0 1-1.158 13.528v-9.476a1.293 1.293 0 0 0-.647-1.13zm3.35-5.043c-.059-.037-.162-.099-.236-.141l-7.965-4.6a1.298 1.298 0 0 0-1.308 0l-9.723 5.614v-3.888a.12.12 0 0 1 .048-.103l8.05-4.645a7.497 7.497 0 0 1 11.135 7.763zm-21.063 6.929l-3.367-1.944a.12.12 0 0 1-.065-.092v-9.299a7.497 7.497 0 0 1 12.293-5.756 6.94 6.94 0 0 0-.236.134l-7.965 4.6a1.294 1.294 0 0 0-.654 1.132l-.006 11.225zm1.829-3.943l4.33-2.501 4.332 2.5v4.999l-4.331 2.5-4.331-2.5V18z"/></svg>
                )},
                { name: "Qdrant",      color: "#DC244C", icon: (
                  <svg viewBox="0 0 64 64" className="w-5 h-5 shrink-0"><polygon points="32,4 58,18 58,46 32,60 6,46 6,18" fill="#DC244C"/><polygon points="32,4 58,18 32,32" fill="#ff6b8a" opacity=".7"/><polygon points="6,18 32,32 32,60" fill="#a0001c" opacity=".7"/><polygon points="32,32 58,18 58,46" fill="#c0002a" opacity=".6"/><circle cx="32" cy="32" r="10" fill="white" opacity=".9"/></svg>
                )},
                { name: "Docker",      color: "#2496ED", icon: (
                  <svg viewBox="0 0 256 190" className="w-5 h-5 shrink-0"><path fill="#2496ED" d="M250 87.6c-4.4-3-14.7-4.2-22.6-2.6-.9-8.5-6.1-15.9-15.8-22.6l-5.4-3.5-3.5 5.4c-4.4 7-6.6 16.6-5.9 25.8a38 38 0 0 0 5.2 13.7c-7.6 4.2-20 5.3-22.5 5.4H18.4C8.4 109.6 0 118 0 128.2a75 75 0 0 0 1.2 13.6C4.7 160 13 173 24.8 181.7c13.3 9.8 34.9 15 59.4 15 11.4 0 22.7-1 33.7-3a133 133 0 0 0 44.6-17.4 117 117 0 0 0 30.5-29.6c14.8-21 23.7-44.5 29.3-65.2 17 1 28.4-4.2 34.3-9.1 3.7-3 5.8-5.9 6.6-7.6l2.6-6-15.8-10.2Z"/><path fill="#2496ED" d="M28.4 87.6h24.4V64H28.4v23.6Zm27.2 0h24.4V64H55.6v23.6Zm27.3 0h24.4V64H82.9v23.6Zm27.2 0h24.4V64h-24.4v23.6Zm-54.4-26h24.4V38H55.7v23.6Zm27.2 0h24.4V38H82.9v23.6Zm27.2 0h24.4V38h-24.4v23.6Zm27.3 0h24.4V38h-24.4v23.6Zm0 26h24.4V64h-24.4v23.6Z"/></svg>
                )},
                { name: "Tailwind",    color: "#06B6D4", icon: (
                  <svg viewBox="0 0 256 154" className="w-5 h-5 shrink-0"><path fill="#06B6D4" fillRule="evenodd" d="M128 0C93.867 0 72.533 17.067 64 51.2 76.8 34.133 91.733 27.733 108.8 32c9.737 2.434 16.697 9.499 24.401 17.318C145.751 62.057 160.275 76.8 192 76.8c34.133 0 55.467-17.067 64-51.2-12.8 17.067-27.733 23.467-44.8 19.2-9.737-2.434-16.697-9.499-24.401-17.318C174.249 14.743 159.725 0 128 0ZM64 76.8C29.867 76.8 8.533 93.867 0 128c12.8-17.067 27.733-23.467 44.8-19.2 9.737 2.434 16.697 9.499 24.401 17.318C81.751 138.857 96.275 153.6 128 153.6c34.133 0 55.467-17.067 64-51.2-12.8 17.067-27.733 23.467-44.8 19.2-9.737-2.434-16.697-9.499-24.401-17.318C110.249 91.543 95.725 76.8 64 76.8Z"/></svg>
                )},
                { name: "SQLAlchemy",  color: "#D71F00", icon: (
                  <svg viewBox="0 0 256 256" className="w-5 h-5 shrink-0"><rect width="256" height="256" rx="20" fill="#D71F00"/><text x="128" y="148" textAnchor="middle" fill="white" fontSize="60" fontWeight="bold" fontFamily="monospace">SA</text></svg>
                )},
              ].map(({ name, color, icon }) => (
                <div
                  key={name}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-[var(--color-border)] bg-white/60 text-[length:var(--text-xs)] font-medium text-[color:var(--color-ink)] shadow-[var(--shadow-xs)] hover:shadow-[var(--shadow-sm)] transition-shadow"
                >
                  {icon}
                  <span>{name}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Bottom bar */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 pt-4 border-t border-[var(--color-border)] text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]">
            <span>© {new Date().getFullYear()} AIJobMatch · aijobmatch.ru</span>
          </div>

        </div>
      </footer>
    </main>
  );
}

function Analysis({ data, expectedSalaryMin, expectedSalaryMax }: {
  data: Record<string, unknown>;
  expectedSalaryMin?: number | null;
  expectedSalaryMax?: number | null;
}) {
  const hardSkills = asStringArray(data.hard_skills);
  const softSkills = asStringArray(data.soft_skills);
  const tools = asStringArray(data.tools);
  const domains = asStringArray(data.domains);
  const strengths = asStringArray(data.strengths);
  const weaknesses = asStringArray(data.weaknesses);
  const riskFlags = asStringArray(data.risk_flags);
  const recommendations = asStringArray(data.recommendations);
  const totalExperience = asNumber(data.total_experience_years);
  const seniorityConfidence = asNumber(data.seniority_confidence);
  const [detailsOpen, setDetailsOpen] = useState(false);

  const role = asText(data.target_role, '') || asText(data.specialization, '') || '—';
  const grade = asText(data.seniority, '—');
  const salaryDisplay =
    expectedSalaryMin || expectedSalaryMax
      ? [
          expectedSalaryMin ? new Intl.NumberFormat('ru-RU').format(expectedSalaryMin) : null,
          expectedSalaryMax ? new Intl.NumberFormat('ru-RU').format(expectedSalaryMax) : null,
        ]
          .filter(Boolean)
          .join(' – ') + ' ₽'
      : 'не указано';

  return (
    <div className="analysis">
      {/* Compact summary — always visible */}
      <div className="grid gap-1.5 pt-1 pb-2">
        <div className="flex justify-between gap-4">
          <span className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">Роль</span>
          <span className="text-[length:var(--text-sm)] text-[color:var(--color-ink)] text-right">{role}</span>
        </div>
        <div className="flex justify-between gap-4">
          <span className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">Грейд</span>
          <span className="text-[length:var(--text-sm)] text-[color:var(--color-ink)]">{grade}</span>
        </div>
        {totalExperience !== null ? (
          <div className="flex justify-between gap-4">
            <span className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">Опыт</span>
            <span className="text-[length:var(--text-sm)] text-[color:var(--color-ink)]">{totalExperience} лет</span>
          </div>
        ) : null}
        {hardSkills.length > 0 ? (
          <div className="flex justify-between items-start gap-4">
            <span className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)] shrink-0">Топ навыки</span>
            <span className="text-[length:var(--text-sm)] text-[color:var(--color-ink)] text-right">{hardSkills.slice(0, 5).join(', ')}</span>
          </div>
        ) : null}
        {(expectedSalaryMin || expectedSalaryMax) ? (
          <div className="flex justify-between gap-4">
            <span className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">Зарплата</span>
            <span className="text-[length:var(--text-sm)] font-[var(--font-mono)] text-[color:var(--color-ink)]">{salaryDisplay}</span>
          </div>
        ) : null}
      </div>

      <Collapsible open={detailsOpen} onOpenChange={setDetailsOpen}>
        <CollapsibleTrigger className="group flex items-center gap-1.5 text-left py-1.5 text-[length:var(--text-sm)] font-semibold text-[color:var(--color-accent)] hover:opacity-75 transition-opacity">
          <span>{detailsOpen ? 'Свернуть' : 'Подробности профиля'}</span>
          <span className="no-underline text-[length:var(--text-xs)] transition-transform duration-[var(--duration-fast)] group-data-[state=open]:rotate-180">▼</span>
        </CollapsibleTrigger>
        <CollapsibleContent className="data-[state=open]:animate-slide-down">
          <div className="analysis-section">
            <h4>Краткий профиль</h4>
            <p>{asText(data.summary, 'Описание пока недоступно')}</p>
          </div>
          <PillList title="Hard skills" items={hardSkills} />
          <PillList title="Soft skills" items={softSkills} />
          <PillList title="Инструменты и технологии" items={tools} />
          <PillList title="Домены и отрасли" items={domains} />
          <List title="Сильные стороны" items={strengths} />
          <List title="Зоны роста" items={weaknesses} />
          <List title="Риски" items={riskFlags} />
          <List title="Рекомендации" items={recommendations} />
          <button
            type="button"
            onClick={() => setDetailsOpen(false)}
            className="mt-2 flex items-center gap-1.5 text-left py-1.5 text-[length:var(--text-sm)] font-semibold text-[color:var(--color-accent)] hover:opacity-75 transition-opacity"
          >
            <span>Свернуть</span>
            <span className="text-[length:var(--text-xs)] rotate-180">▼</span>
          </button>
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
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

function PillList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="analysis-section">
      <h4>{title}</h4>
      <div className="flex flex-wrap gap-1.5 mt-1">
        {items.map((item) => (
          <span
            key={item}
            className="inline-block px-2.5 py-0.5 rounded-full text-[length:var(--text-xs)] font-medium bg-[color-mix(in_srgb,var(--color-accent)_13%,transparent)] text-[color:var(--color-ink)] border border-[color-mix(in_srgb,var(--color-accent)_28%,transparent)]"
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}
