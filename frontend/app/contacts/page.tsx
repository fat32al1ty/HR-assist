export default function ContactsPage() {
  return (
    <main className="page">
      <section className="main">
        <div className="max-w-[780px] mx-auto text-center py-20 px-6">
          <span className="inline-block mb-4 px-4 py-1.5 rounded-full border border-[var(--color-border)] bg-white/70 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] font-medium">
            Контакты
          </span>
          <h1 className="text-[length:var(--text-display)] font-bold tracking-[-0.03em] leading-[var(--leading-tight)] text-[color:var(--color-ink)] mb-6">
            Свяжитесь со мной
          </h1>
          <p className="text-[length:var(--text-xl)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
            Обычно отвечаю в течение 24 часов.
          </p>
        </div>

        <div className="max-w-[480px] mx-auto px-6 pb-24 flex flex-col gap-4">
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-5 flex gap-4 items-center">
            <span className="text-2xl shrink-0">💬</span>
            <div>
              <p className="text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)] uppercase tracking-wider mb-0.5">Telegram</p>
              <a
                href="https://t.me/artem_khirev"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[length:var(--text-base)] font-medium text-[color:var(--color-accent)] hover:underline"
              >
                @artem_khirev
              </a>
            </div>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-5 flex gap-4 items-center">
            <span className="text-2xl shrink-0">✉️</span>
            <div>
              <p className="text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)] uppercase tracking-wider mb-0.5">Email</p>
              <a
                href="mailto:artyom.khiryov@yandex.ru"
                className="text-[length:var(--text-base)] font-medium text-[color:var(--color-accent)] hover:underline"
              >
                artyom.khiryov@yandex.ru
              </a>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
