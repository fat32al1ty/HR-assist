export default function CookiesPage() {
  return (
    <main className="page">
      <section className="main">
        {/* Hero */}
        <div className="max-w-[780px] mx-auto text-center py-20 px-6">
          <span className="inline-block mb-4 px-4 py-1.5 rounded-full border border-[var(--color-border)] bg-white/70 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] font-medium">
            Правовое
          </span>
          <h1 className="text-[length:var(--text-display)] font-bold tracking-[-0.03em] leading-[var(--leading-tight)] text-[color:var(--color-ink)] mb-4">
            Cookies и локальное хранилище
          </h1>
          <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)]">
            Последнее обновление: 24 апреля 2026 г.
          </p>
        </div>

        {/* Контент */}
        <div className="max-w-[780px] mx-auto px-6 pb-20 space-y-6">
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Что используется
            </h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              Сервис использует только технически необходимые cookies и браузерное локальное
              хранилище для хранения токена сессии после входа. Без этих данных невозможно
              поддерживать состояние авторизации между страницами.
            </p>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Чего не используется
            </h2>
            <ul className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)] space-y-1 list-disc pl-6">
              <li>системы веб-аналитики (Яндекс.Метрика, Google Analytics и т. п.)</li>
              <li>рекламные cookies и системы ретаргетинга</li>
              <li>cookies сторонних социальных сетей</li>
            </ul>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Управление
            </h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              Cookies и локальное хранилище можно очистить через настройки браузера. Это приведёт
              к выходу из учётной записи. Повторный вход полностью восстановит работу сервиса.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
