'use client';

import { FormEvent, useEffect, useState } from 'react';
import {
  excludeFeedbackVacancies,
  normalizeVacancyId,
  removeVacancyFromList,
  removeVacancyMatchEntry
} from '../lib/vacancyMatching';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'http://localhost:8000');
const MIN_PROGRESS_VISIBLE_MS = 1400;
const RECOMMEND_TIMEOUT_MS = 540000;
const LAST_JOB_ID_STORAGE_KEY = 'last_recommendation_job_id';

type Resume = {
  id: number;
  original_filename: string;
  status: string;
  extracted_text: string | null;
  analysis: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
};
type AuthFormMode = 'login' | 'register' | 'reset';

type VacancyMatch = {
  vacancy_id: number;
  title: string;
  source_url: string;
  company: string | null;
  location: string | null;
  similarity_score: number;
  profile: Record<string, unknown> | null;
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
};

type DashboardStatsResponse = {
  generated_at: string;
  qdrant: {
    status: string;
    collections: string[];
    indexed_vacancies: number;
    profiled_vacancies: number;
    profile_coverage_percent: number;
    preference_positive_ready: boolean;
    preference_negative_ready: boolean;
  };
  resume: {
    resume_id: number;
    resume_embedded: boolean;
    target_role: string | null;
    specialization: string | null;
    indexed_vacancies: number;
    vector_candidates_top300: number;
    relevant_over_55_top300: number;
    selected_count: number;
    disliked_count: number;
    last_job_id: string | null;
    last_job_status: string | null;
    last_job_matches: number | null;
    last_job_sources: number | null;
    last_job_analyzed: number | null;
    last_job_created_at: string | null;
    last_query: string | null;
  } | null;
};

type WarmupStatusResponse = {
  enabled: boolean;
  running: boolean;
  cycle: number;
  last_started_at: string | null;
  last_finished_at: string | null;
  last_duration_seconds: number | null;
  last_error: string | null;
  last_queries: string[];
  last_metrics: {
    fetched?: number;
    prefiltered?: number;
    analyzed?: number;
    filtered?: number;
    indexed?: number;
    failed?: number;
    already_indexed_skipped?: number;
    backfill_considered?: number;
    backfill_profiled?: number;
    backfill_filtered?: number;
    backfill_failed?: number;
  };
  interval_seconds: number;
  queries_per_cycle: number;
  discover_count: number;
  max_analyzed_per_query: number;
  cycle_timeout_seconds: number;
  profile_backfill_enabled: boolean;
  profile_backfill_limit_per_cycle: number;
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

function scoreToPercent(score: number): string {
  return `${Math.round(score * 100)}%`;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function stageLabel(stage: string): string {
  switch (stage) {
    case 'queued':
      return 'Задача в очереди...';
    case 'collecting':
      return 'Собираем и фильтруем вакансии...';
    case 'matching':
      return 'Выполняем matching с резюме...';
    case 'finalizing':
      return 'Формируем итоговую выдачу...';
    case 'done':
      return 'Готово';
    case 'failed':
      return 'Ошибка';
    default:
      return 'Выполняется...';
  }
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
  const [token, setToken] = useState<string | null>(null);
  const [authFormMode, setAuthFormMode] = useState<AuthFormMode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [betaKey, setBetaKey] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [resumes, setResumes] = useState<Resume[]>([]);
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
  const [hiddenMatchIds, setHiddenMatchIds] = useState<number[]>([]);
  const [dashboardStats, setDashboardStats] = useState<DashboardStatsResponse | null>(null);
  const [warmupStatus, setWarmupStatus] = useState<WarmupStatusResponse | null>(null);

  useEffect(() => {
    const storedToken = window.localStorage.getItem('access_token');
    const storedJobId = readStoredJobId();
    if (storedJobId) {
      setCurrentJobId(storedJobId);
    }
    if (storedToken) {
      setToken(storedToken);
    }
  }, []);

  useEffect(() => {
    if (!token) {
      return;
    }
    void loadResumes(token);
    void loadSelectedVacancies();
    void loadDislikedVacancies();
  }, [token]);

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
    return (
      `Источников: ${metrics.fetched || 0}, проанализировано: ${metrics.analyzed || 0}, ` +
      `уже в индексе: ${metrics.already_indexed_skipped || 0}, отфильтровано: ${metrics.filtered || 0}, ` +
      `проиндексировано: ${metrics.indexed || 0}.`
    );
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

    if (status.status === 'completed') {
      const visibleMatches = excludeFeedbackVacancies(
        status.matches || [],
        dislikedVacancies,
        selectedVacancies,
        hiddenMatchIds
      );
      setMatches(visibleMatches);
      const metricsInfo = formatMetricsInfo(metrics);
      setMatchingMessage(
        visibleMatches.length > 0
          ? `Найдено совпадений: ${visibleMatches.length}. ${metricsInfo}`
          : `Подходящие вакансии не найдены. ${metricsInfo}`
      );
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
    window.localStorage.removeItem('access_token');
    setToken(null);
    setResumes([]);
    setMatches([]);
    setHiddenMatchIds([]);
    setSelectedVacancies([]);
    setDislikedVacancies([]);
    setExpandedResumeIds({});
    setSelectedResumeId(null);
    setMatchingProgress(0);
    setMatchingStage('');
    setDashboardStats(null);
    setWarmupStatus(null);
    setOpenaiUsageMessage('');
    setLastMatchingQuery('');
    setLastSources([]);
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
      throw new Error(payload.detail || 'Запрос не выполнен');
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
        await fetch(`${API_BASE_URL}/api/auth/password/reset`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, new_password: newPassword, beta_key: betaKey })
        }).then(async (response) => {
          if (!response.ok) {
            const payload = await response.json().catch(() => ({ detail: 'Не удалось обновить пароль' }));
            throw new Error(payload.detail || 'Не удалось обновить пароль');
          }
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
        const registerResponse = await fetch(`${API_BASE_URL}/api/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, password, full_name: null, beta_key: betaKey })
        });
        if (!registerResponse.ok) {
          const payload = await registerResponse
            .json()
            .catch(() => ({ detail: 'Не удалось создать аккаунт' }));
          throw new Error(payload.detail || 'Не удалось создать аккаунт');
        }
      }

      const loginResponse = await fetch(`${API_BASE_URL}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });

      if (!loginResponse.ok) {
        const payload = await loginResponse.json().catch(() => ({ detail: 'Не удалось войти' }));
        throw new Error(payload.detail || 'Не удалось войти');
      }

      const auth = (await loginResponse.json()) as { access_token: string };
      window.localStorage.setItem('access_token', auth.access_token);
      setToken(auth.access_token);
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

  async function loadSelectedVacancies() {
    try {
      const data = await request<VacancyMatch[]>('/api/vacancies/feedback/selected');
      setSelectedVacancies(data);
    } catch {
      setSelectedVacancies([]);
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

  async function recommendVacancies() {
    if (!selectedResumeId) {
      setMatchingMessage('Select a resume first.');
      return;
    }

    setMatchingBusy(true);
    setMatchingProgress(0);
    setMatchingStage('');
    setOpenaiUsageMessage('');
    setLastMatchingQuery('');
    setLastSources([]);
    setPersistentJobId(null);
    setMatchingMessage('Quick matching from indexed vacancies...');

    try {
      const quickMatches = await request<VacancyMatch[]>(`/api/vacancies/match/${selectedResumeId}?limit=20`);
      const filteredQuickMatches = excludeFeedbackVacancies(
        quickMatches,
        dislikedVacancies,
        selectedVacancies,
        hiddenMatchIds
      );
      setMatches(filteredQuickMatches);
      if (filteredQuickMatches.length > 0) {
        setMatchingMessage(`Found matches: ${filteredQuickMatches.length}. Quick mode uses current index only.`);
      } else {
        setMatchingMessage('No matches in current index. Run "Update Vacancy Index" to expand coverage.');
      }
    } catch (error) {
      setMatchingMessage(error instanceof Error ? error.message : 'Quick matching failed');
    } finally {
      setMatchingBusy(false);
      await loadDashboardStats(selectedResumeId);
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
          setMatchingMessage(`Matching progress: ${formatMetricsInfo(status.metrics || {})}`);
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
          setMatchingMessage(`Matching progress: ${formatMetricsInfo(status.metrics || {})}`);
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
      <header className="topbar">
        <div className="topbar-inner">
          <div className="brand">
            <img className="brand-logo" src="/hr-ai-logo.png" alt="HR Помощник" />
            <span>HR Помощник</span>
            <a
              className="app-version"
              href={`https://github.com/fat32al1ty/HR-assist/releases`}
              target="_blank"
              rel="noreferrer"
              title="Текущая версия сборки"
            >
              {process.env.NEXT_PUBLIC_APP_VERSION ?? 'dev'}
            </a>
          </div>
          {token ? (
            <button className="secondary" onClick={logout}>
              Выйти
            </button>
          ) : null}
        </div>
      </header>

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
              <p className="panel-note">Поддерживаются PDF и DOCX. После загрузки создается структурированный профиль для matching.</p>
              <form className="form" onSubmit={uploadResume}>
                <input
                  type="file"
                  accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                  onChange={(event) => setFile(event.target.files?.[0] || null)}
                />
                <button className="primary" disabled={busy}>
                  Проанализировать
                </button>
              </form>
              {message ? <p className="message">{message}</p> : null}

              <div className="stats-box">
                <h3>Qdrant stats</h3>
                {dashboardStats ? (
                  <ul className="stats-list">
                    <li>Status: {dashboardStats.qdrant.status}</li>
                    <li>Collections: {dashboardStats.qdrant.collections.length}</li>
                    <li>Indexed vacancies: {dashboardStats.qdrant.indexed_vacancies}</li>
                    <li>Profiled vacancies: {dashboardStats.qdrant.profiled_vacancies}</li>
                    <li>Coverage: {dashboardStats.qdrant.profile_coverage_percent}%</li>
                    <li>
                      Pref vectors: +{dashboardStats.qdrant.preference_positive_ready ? 'yes' : 'no'} / -
                      {dashboardStats.qdrant.preference_negative_ready ? 'yes' : 'no'}
                    </li>
                  </ul>
                ) : (
                  <p className="panel-note">No stats yet.</p>
                )}

                {dashboardStats?.resume ? (
                  <>
                    <h3>Resume scope</h3>
                    <ul className="stats-list">
                      <li>Resume vector: {dashboardStats.resume.resume_embedded ? 'ready' : 'missing'}</li>
                      <li>Role: {dashboardStats.resume.target_role || 'n/a'}</li>
                      <li>Specialization: {dashboardStats.resume.specialization || 'n/a'}</li>
                      <li>Vector candidates (top300): {dashboardStats.resume.vector_candidates_top300}</li>
                      <li>Relevant &gt;=55%: {dashboardStats.resume.relevant_over_55_top300}</li>
                      <li>Selected / Disliked: {dashboardStats.resume.selected_count} / {dashboardStats.resume.disliked_count}</li>
                      <li>Last job status: {dashboardStats.resume.last_job_status || 'n/a'}</li>
                      <li>Last job matches: {dashboardStats.resume.last_job_matches ?? 0}</li>
                      <li>Last job analyzed: {dashboardStats.resume.last_job_analyzed ?? 0}</li>
                      <li>Last job sources: {dashboardStats.resume.last_job_sources ?? 0}</li>
                    </ul>
                  </>
                ) : (
                  <p className="panel-note">Select resume to see scoped stats.</p>
                )}

                <h3>Background warmup</h3>
                {warmupStatus ? (
                  <ul className="stats-list">
                    <li>Status: {warmupStatus.enabled ? (warmupStatus.running ? 'running' : 'idle') : 'disabled'}</li>
                    <li>Cycle: {warmupStatus.cycle}</li>
                    <li>Interval: {warmupStatus.interval_seconds}s</li>
                    <li>Last duration: {warmupStatus.last_duration_seconds ?? 0}s</li>
                    <li>Last indexed: {warmupStatus.last_metrics.indexed ?? 0}</li>
                    <li>Last analyzed: {warmupStatus.last_metrics.analyzed ?? 0}</li>
                    <li>Last fetched: {warmupStatus.last_metrics.fetched ?? 0}</li>
                    <li>Backfill profiled: {warmupStatus.last_metrics.backfill_profiled ?? 0}</li>
                    <li>Backfill considered: {warmupStatus.last_metrics.backfill_considered ?? 0}</li>
                    <li>Queries per cycle: {warmupStatus.queries_per_cycle}</li>
                    <li>Max analyzed/query: {warmupStatus.max_analyzed_per_query}</li>
                    <li>Backfill/cycle: {warmupStatus.profile_backfill_enabled ? warmupStatus.profile_backfill_limit_per_cycle : 0}</li>
                    {warmupStatus.last_error ? <li>Last error: {warmupStatus.last_error}</li> : null}
                  </ul>
                ) : (
                  <p className="panel-note">Warmup status unavailable.</p>
                )}
              </div>
            </aside>

            <div className="workspace-main">
              <section className="panel">
                <h2>Мое резюме</h2>
                <div className="resume-list">
                  {resumes.length === 0 ? <p className="empty-state">Пока нет загруженных резюме.</p> : null}
                  {resumes.map((resume) => (
                    <article className="resume-item" key={resume.id}>
                      <div className="resume-item-head">
                        <div>
                          <h3>{resume.original_filename}</h3>
                          <span className={`status ${resume.status}`}>{statusLabels[resume.status] || resume.status}</span>
                        </div>
                        <div className="resume-actions">
                          <button className="secondary resume-toggle" disabled={busy} onClick={() => toggleResumeDetails(resume.id)}>
                            {expandedResumeIds[resume.id] ? 'Свернуть' : 'Показать детали'}
                          </button>
                          <button className="danger" disabled={busy} onClick={() => void deleteResume(resume.id)}>
                            Удалить
                          </button>
                        </div>
                      </div>
                      {resume.error_message ? <p className="message">{resume.error_message}</p> : null}
                      {resume.analysis && expandedResumeIds[resume.id] ? <Analysis data={resume.analysis} /> : null}
                    </article>
                  ))}
                </div>
              </section>

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
                  <button className="secondary" onClick={recommendVacancies} disabled={matchingBusy}>
                    Быстрый подбор
                  </button>
                  <button className="primary" onClick={refreshVacancyIndex} disabled={matchingBusy}>
                    Обновить базу вакансий
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
                  {visibleMatches.map((match) => {
                    const matchedSkills = matchedSkillsFromMatch(match);
                    const matchedRequirements = matchedRequirementsFromMatch(match);
                    const missingRequirements = missingRequirementsFromMatch(match);
                    const matchedEntries = matchedRequirements.length > 0 ? matchedRequirements : matchedSkills;
                    return (
                    <article className="vacancy-item" key={match.vacancy_id}>
                      <h3>{match.title}</h3>
                      <p className="meta">
                        {match.company || 'Компания не указана'}
                        {' • '}
                        {match.location || 'Локация не указана'}
                      </p>
                      <p className="match-score">Релевантность: {scoreToPercent(match.similarity_score)}</p>
                      <div className="fit-grid">
                        <div className="fit-box fit-matched">
                          <p className="fit-title">Ты подходишь</p>
                          {matchedEntries.length > 0 ? (
                            <ul>
                              {matchedEntries.map((item) => (
                                <li key={`${match.vacancy_id}-match-${item}`}>{item}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="fit-empty">совпадение по ключевым словам в описании</p>
                          )}
                        </div>
                        <div className="fit-box fit-missing">
                          <p className="fit-title">Чего не хватает</p>
                          {missingRequirements.length > 0 ? (
                            <ul>
                              {missingRequirements.map((item) => (
                                <li key={`${match.vacancy_id}-miss-${item}`}>{item}</li>
                              ))}
                            </ul>
                          ) : (
                            <p className="fit-empty">совпадение по всем указанным требованиям</p>
                          )}
                        </div>
                      </div>
                      <div className="vacancy-actions">
                        <a href={match.source_url} target="_blank" rel="noreferrer">
                          Открыть источник
                        </a>
                        <button className="secondary" disabled={matchingBusy} onClick={() => void likeVacancy(match)}>
                          Плюс
                        </button>
                        <button className="danger" disabled={matchingBusy} onClick={() => void dislikeVacancy(match)}>
                          Минус
                        </button>
                      </div>
                    </article>
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
