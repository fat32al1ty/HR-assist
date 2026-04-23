import Link from 'next/link';

const STATUSES = [
  { label: 'Отправлено', desc: 'Отклик зафиксирован', color: 'var(--color-info)' },
  { label: 'Просмотрено', desc: 'Рекрутер открыл резюме', color: 'var(--color-warning)' },
  { label: 'Собеседование', desc: 'Вас позвали на встречу', color: 'var(--color-accent)' },
  { label: 'Оффер', desc: 'Получен оффер', color: 'var(--color-success)' },
] as const;

export default function FunnelPage() {
  return (
    <main className="page">
      <section className="main">
        {/* Hero */}
        <div className="max-w-[780px] mx-auto text-center py-20 px-6">
          <span className="inline-block mb-4 px-4 py-1.5 rounded-full border border-[var(--color-border)] bg-white/70 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] font-medium">
            Воронка откликов
          </span>
          <h1 className="text-[length:var(--text-display)] font-bold tracking-[-0.03em] leading-[var(--leading-tight)] text-[color:var(--color-ink)] mb-6">
            Следите за каждым откликом<br />в одном месте
          </h1>
          <p className="text-[length:var(--text-xl)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
            Больше не нужно держать таблицу в голове. HR консультант отслеживает статус каждой заявки и подсказывает следующий шаг.
          </p>
        </div>

        {/* Степпер */}
        <div className="max-w-[1100px] mx-auto px-6 py-16">
          <h2 className="text-[length:var(--text-3xl)] font-bold text-[color:var(--color-ink)] text-center mb-14 tracking-[-0.02em]">
            4 статуса воронки
          </h2>
          <div className="relative flex flex-col md:flex-row items-start md:items-center gap-0">
            {STATUSES.map(({ label, desc, color }, idx) => (
              <div key={label} className="flex flex-col md:flex-row items-start md:items-center flex-1 min-w-0">
                <div className="flex flex-col items-center md:items-start gap-3 w-full px-4 py-6 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] md:rounded-none md:border-0 md:shadow-none md:bg-transparent">
                  <div
                    className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-[length:var(--text-base)] shrink-0"
                    style={{ backgroundColor: color }}
                  >
                    {idx + 1}
                  </div>
                  <div>
                    <p className="font-semibold text-[color:var(--color-ink)] text-[length:var(--text-base)]">{label}</p>
                    <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">{desc}</p>
                  </div>
                </div>
                {idx < STATUSES.length - 1 && (
                  <div className="hidden md:block shrink-0 text-[color:var(--color-ink-secondary)] text-xl px-2">→</div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Сопроводительное */}
        <div className="max-w-[780px] mx-auto px-6 py-8">
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-8 text-center">
            <span className="text-4xl mb-4 block">✍️</span>
            <h3 className="text-[length:var(--text-2xl)] font-bold text-[color:var(--color-ink)] mb-3 tracking-[-0.02em]">
              Сопроводительное за одну кнопку
            </h3>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)] max-w-[520px] mx-auto">
              AI составляет персонализированное сопроводительное письмо под каждую вакансию — с учётом вашего резюме и требований позиции. Вам остаётся только нажать «Отправить».
            </p>
          </div>
        </div>

        {/* CTA */}
        <div className="max-w-[780px] mx-auto px-6 py-16 text-center">
          <Link
            href="/"
            className="inline-block px-10 py-4 rounded-[var(--radius-lg)] bg-[var(--color-accent)] text-[color:var(--color-on-accent)] font-bold text-[length:var(--text-lg)] shadow-[var(--shadow-sm)] transition-opacity hover:opacity-90"
          >
            Начать — это бесплатно
          </Link>
        </div>
      </section>
    </main>
  );
}
