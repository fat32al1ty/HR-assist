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
            Политика cookies
          </h1>
          <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)]">
            Последнее обновление: 23 апреля 2026 г.
          </p>
        </div>

        {/* Контент */}
        <div className="max-w-[780px] mx-auto px-6 pb-20 space-y-8">
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">Что такое cookies</h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              Cookies — небольшие текстовые файлы, которые сохраняются в вашем браузере при посещении сайта. Они позволяют сайту запоминать ваши предпочтения и поддерживать сессию входа.
            </p>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-4">Какие cookies мы используем</h2>
            <div className="space-y-4">
              {[
                {
                  type: 'Сессионные',
                  desc: 'Необходимы для работы авторизации. Хранят токен сессии на время вашего визита. Удаляются при закрытии браузера или выходе из аккаунта.',
                  required: true,
                },
                {
                  type: 'Аналитические',
                  desc: 'Анонимные данные об использовании сервиса: какие страницы посещались, сколько времени занял анализ резюме. Помогают нам улучшать продукт. Не содержат персональных данных.',
                  required: false,
                },
              ].map(({ type, desc, required }) => (
                <div key={type} className="flex gap-4 items-start">
                  <span
                    className={`shrink-0 mt-0.5 text-[length:var(--text-xs)] font-bold px-2 py-0.5 rounded-full whitespace-nowrap ${
                      required
                        ? 'bg-[var(--color-success-subtle)] text-[color:var(--color-success)]'
                        : 'bg-[var(--color-accent-subtle)] text-[color:var(--color-accent)]'
                    }`}
                  >
                    {required ? 'Обязательные' : 'Аналитика'}
                  </span>
                  <div>
                    <p className="font-semibold text-[color:var(--color-ink)] text-[length:var(--text-base)] mb-1">{type}</p>
                    <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">Как управлять cookies</h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              Вы можете отключить cookies в настройках браузера. Обратите внимание: отключение сессионных cookies приведёт к невозможности входа в аккаунт. Аналитические cookies можно отключить без потери функциональности сервиса.
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
