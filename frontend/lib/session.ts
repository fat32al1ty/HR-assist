'use client';

import {
  createContext,
  useCallback,
  useContext,
  useState,
} from 'react';

import type { Resume } from '@/types/resume';
export type { Resume };

// ──────────────────────────────────────────────────────────────────────────────
// Shape
// ──────────────────────────────────────────────────────────────────────────────

export type SessionUser = {
  id: number;
  email: string;
  full_name: string | null;
  is_admin: boolean;
};

export type Session = {
  token: string | null;
  user: SessionUser | null;
  activeResumeLabel: string | null;
  setActiveResumeLabel: (label: string | null) => void;
  setSession: (s: { token: string; user: SessionUser }) => void;
  clearSession: (message?: string) => void;
  /** Transient message set by clearSession — page.tsx reads this once. */
  pendingMessage: string | null;
  consumePendingMessage: () => void;
  /** Resume list — set by page.tsx after each load/mutate. */
  resumes: Resume[];
  setResumes: (resumes: Resume[]) => void;
  /**
   * Activate a resume profile. page.tsx registers its implementation via
   * setActivateResumeProfile after it has access to all local state.
   */
  activateResumeProfile: (id: number) => Promise<void>;
  setActivateResumeProfile: (fn: (id: number) => Promise<void>) => void;
};

// ──────────────────────────────────────────────────────────────────────────────
// localStorage keys (must match the existing conventions used in page.tsx)
// ──────────────────────────────────────────────────────────────────────────────
const TOKEN_KEY = 'access_token';
const JOB_ID_KEY = 'last_recommendation_job_id';

// ──────────────────────────────────────────────────────────────────────────────
// Context
// ──────────────────────────────────────────────────────────────────────────────
import { type ReactNode } from 'react';
import React from 'react';

const noop = () => Promise.resolve();

const SessionContext = createContext<Session>({
  token: null,
  user: null,
  activeResumeLabel: null,
  setActiveResumeLabel: () => undefined,
  setSession: () => undefined,
  clearSession: () => undefined,
  pendingMessage: null,
  consumePendingMessage: () => undefined,
  resumes: [],
  setResumes: () => undefined,
  activateResumeProfile: noop,
  setActivateResumeProfile: () => undefined,
});

// ──────────────────────────────────────────────────────────────────────────────
// Provider
// ──────────────────────────────────────────────────────────────────────────────
export function SessionProvider({ children }: { children: ReactNode }) {
  // Lazy initial state — reads from localStorage on first render (client only).
  // Using a function initializer avoids triggering an extra render and
  // satisfies the react-hooks/set-state-in-effect rule.
  const [token, setToken] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    try {
      return window.localStorage.getItem(TOKEN_KEY) ?? null;
    } catch {
      return null;
    }
  });
  const [user, setUser] = useState<SessionUser | null>(null);
  const [activeResumeLabel, setActiveResumeLabel] = useState<string | null>(null);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [resumes, setResumes] = useState<Resume[]>([]);
  // Store the page-registered activateResumeProfile in state as a wrapped
  // function. React requires `setState(fn)` to be called with `() => fn`
  // when the value itself is a function, to avoid treating it as an updater.
  const [activateResumeProfile, setActivateResumeProfileState] = useState<
    (id: number) => Promise<void>
  >(() => noop);
  const setActivateResumeProfile = useCallback(
    (fn: (id: number) => Promise<void>) => {
      setActivateResumeProfileState(() => fn);
    },
    []
  );

  const setSession = useCallback(
    (s: { token: string; user: SessionUser }) => {
      try {
        window.localStorage.setItem(TOKEN_KEY, s.token);
      } catch {
        // ignore
      }
      setToken(s.token);
      setUser(s.user);
    },
    []
  );

  const clearSession = useCallback((message?: string) => {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
      window.localStorage.removeItem(JOB_ID_KEY);
    } catch {
      // ignore
    }
    setToken(null);
    setUser(null);
    setActiveResumeLabel(null);
    if (message) {
      setPendingMessage(message);
    }
  }, []);

  const consumePendingMessage = useCallback(() => {
    setPendingMessage(null);
  }, []);

  const value: Session = {
    token,
    user,
    activeResumeLabel,
    setActiveResumeLabel,
    setSession,
    clearSession,
    pendingMessage,
    consumePendingMessage,
    resumes,
    setResumes,
    activateResumeProfile,
    setActivateResumeProfile,
  };

  return React.createElement(SessionContext.Provider, { value }, children);
}

// ──────────────────────────────────────────────────────────────────────────────
// Hook
// ──────────────────────────────────────────────────────────────────────────────
export function useSession(): Session {
  return useContext(SessionContext);
}
