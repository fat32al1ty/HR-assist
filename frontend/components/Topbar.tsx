'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useSession } from '@/lib/session';
import { resumeDisplayName } from '@/types/resume';

const NAV_ITEMS = [
  { label: 'Подбор', href: '/' },
  { label: 'Отклики', href: '/applications' },
] as const;

export default function Topbar() {
  const {
    token,
    user,
    activeResumeLabel,
    clearSession,
    resumes,
    activateResumeProfile,
  } = useSession();
  const pathname = usePathname();
  const router = useRouter();

  if (!token) {
    return null;
  }

  function handleLogout() {
    clearSession();
    router.push('/');
  }

  const navItems = [
    ...NAV_ITEMS,
    ...(user?.is_admin ? [{ label: 'Админ', href: '/admin' }] : []),
  ];

  const activeResume = resumes.find((r) => r.is_active);

  return (
    <header
      style={{
        borderBottom: '1px solid var(--color-border)',
        background: 'var(--color-surface)',
      }}
    >
      <div
        style={{
          maxWidth: '1200px',
          margin: '0 auto',
          padding: '0 var(--space-6, 1.5rem)',
          height: '52px',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-6, 1.5rem)',
        }}
      >
        {/* Left: product lockup — logo + name + version */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            flexShrink: 0,
          }}
        >
          <Image
            src="/hr-ai-logo.png"
            alt="HR Assist"
            width={24}
            height={24}
            style={{ display: 'block' }}
          />
          <Link
            href="/"
            style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 600,
              fontSize: 'var(--text-lg)',
              color: 'var(--color-ink)',
              textDecoration: 'none',
              letterSpacing: '-0.03em',
            }}
          >
            HR Assist
          </Link>
          <a
            href="https://github.com/fat32al1ty/HR-assist/releases"
            target="_blank"
            rel="noreferrer"
            title="Текущая версия сборки"
            aria-label="Версия приложения"
            style={{
              fontSize: 'var(--text-caption, 0.7rem)',
              color: 'var(--color-ink-secondary)',
              textDecoration: 'none',
              opacity: 0.6,
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.textDecoration = 'underline';
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLAnchorElement).style.textDecoration = 'none';
            }}
          >
            {process.env.NEXT_PUBLIC_APP_VERSION ?? 'dev'}
          </a>
        </div>

        {/* Center: nav tabs */}
        <nav
          style={{
            display: 'flex',
            gap: '4px',
            flex: 1,
          }}
        >
          {navItems.map((item) => {
            const isActive =
              item.href === '/'
                ? pathname === '/'
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                style={{
                  padding: '4px 12px',
                  borderRadius: 'var(--radius-md, 8px)',
                  fontSize: 'var(--text-sm)',
                  fontFamily: 'var(--font-body)',
                  color: isActive ? 'var(--color-accent)' : 'var(--color-ink-secondary)',
                  textDecoration: 'none',
                  fontWeight: isActive ? 600 : 400,
                  borderBottom: isActive ? '2px solid var(--color-accent)' : '2px solid transparent',
                  transition: 'color 120ms, border-color 120ms',
                }}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* Right: profile switcher (if >1 resume) | single-profile label | logout */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 'var(--space-3, 0.75rem)',
            flexShrink: 0,
          }}
        >
          {resumes.length > 1 ? (
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                className="sr-only"
                style={{
                  position: 'absolute',
                  width: '1px',
                  height: '1px',
                  padding: 0,
                  margin: '-1px',
                  overflow: 'hidden',
                  clip: 'rect(0,0,0,0)',
                  whiteSpace: 'nowrap',
                  border: 0,
                }}
              >
                Активный профиль
              </span>
              <select
                value={activeResume?.id ?? ''}
                onChange={(e) => {
                  const nextId = Number(e.target.value);
                  if (Number.isFinite(nextId) && nextId > 0) {
                    void activateResumeProfile(nextId);
                  }
                }}
                style={{
                  fontSize: 'var(--text-sm)',
                  fontFamily: 'var(--font-body)',
                  color: 'var(--color-ink)',
                  background: 'var(--color-surface)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 'var(--radius-md, 8px)',
                  padding: '4px 8px',
                  cursor: 'pointer',
                  maxWidth: '160px',
                }}
              >
                {resumes.map((resume) => (
                  <option key={resume.id} value={resume.id}>
                    {resumeDisplayName(resume)}
                  </option>
                ))}
              </select>
            </label>
          ) : resumes.length === 1 && activeResumeLabel ? (
            <span
              style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--color-ink-muted)',
                fontFamily: 'var(--font-body)',
                maxWidth: '140px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={activeResumeLabel}
            >
              {activeResumeLabel}
            </span>
          ) : null}
          <button
            onClick={handleLogout}
            style={{
              fontSize: 'var(--text-sm)',
              fontFamily: 'var(--font-body)',
              color: 'var(--color-ink-secondary)',
              background: 'none',
              border: '1px solid var(--color-border)',
              borderRadius: 'var(--radius-md, 8px)',
              padding: '4px 10px',
              cursor: 'pointer',
            }}
          >
            Выйти
          </button>
        </div>
      </div>
    </header>
  );
}
