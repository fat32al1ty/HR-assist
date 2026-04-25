'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useSession } from '@/lib/session';
import { resumeDisplayName } from '@/types/resume';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { label: 'Подбор', href: '/' },
  { label: 'Отклики', href: '/applications' },
] as const;

export default function Topbar() {
  const { token, user, activeResumeLabel, clearSession, resumes, activateResumeProfile } = useSession();
  const pathname = usePathname();
  const router = useRouter();

  if (!token) {
    return null;
  }

  function handleLogout() {
    clearSession();
    router.push('/');
  }

  const navItems = [...NAV_ITEMS, ...(user?.is_admin ? [{ label: 'Админ', href: '/admin' }] : [])];
  const activeResume = resumes.find((resume) => resume.is_active);

  return (
    <header className="topbar">
      <div className="topbar-shell">
        <div className="topbar-brand">
          <Image
            src="/brand-preview-assets/aijobmatch-variant2-icon-256.png"
            alt="AI JobMatch"
            width={30}
            height={30}
            className="topbar-brand-logo"
          />
          <Link href="/" className="topbar-brand-link">
            <span style={{ color: 'var(--color-accent)' }}>AI</span> JobMatch
          </Link>
        </div>

        <nav className="topbar-nav">
          {navItems.map((item) => {
            const isActive = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn('topbar-nav-link', isActive && 'topbar-nav-link-active')}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="topbar-right">
          {resumes.length > 1 ? (
            <label className="topbar-profile-switch">
              <span className="sr-only">Активный профиль</span>
              <select
                value={activeResume?.id ?? ''}
                onChange={(event) => {
                  const nextId = Number(event.target.value);
                  if (Number.isFinite(nextId) && nextId > 0) {
                    void activateResumeProfile(nextId);
                  }
                }}
                className="topbar-profile-select"
              >
                {resumes.map((resume) => (
                  <option key={resume.id} value={resume.id}>
                    {resumeDisplayName(resume)}
                  </option>
                ))}
              </select>
            </label>
          ) : resumes.length === 1 && activeResumeLabel ? (
            <span className="topbar-profile-label" title={activeResumeLabel}>
              {activeResumeLabel}
            </span>
          ) : null}

          <button type="button" onClick={handleLogout} className="topbar-logout-btn">
            Выйти
          </button>
        </div>
      </div>
    </header>
  );
}
