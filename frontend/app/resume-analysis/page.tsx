import Link from 'next/link';

export default function ResumeAnalysisPage() {
  return (
    <main className="page">
      <section className="main">
        {/* Hero */}
        <div className="max-w-[780px] mx-auto text-center py-20 px-6">
          <span className="inline-block mb-4 px-4 py-1.5 rounded-full border border-[var(--color-border)] bg-white/70 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] font-medium">
            Анализ резюме
          </span>
          <h1 className="text-[length:var(--text-display)] font-bold tracking-[-0.03em] leading-[var(--leading-tight)] text-[color:var(--color-ink)] mb-6">
            AI видит ваше резюме<br />глазами рекрутера
          </h1>
          <p className="text-[length:var(--text-xl)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
            Узнайте, как рынок воспринимает ваш опыт, какие навыки сигнализируют о грейде и что вас тормозит.
          </p>
        </div>

        {/* Что анализируется */}
        <div className="max-w-[1100px] mx-auto px-6 py-16">
          <h2 className="text-[length:var(--text-3xl)] font-bold text-[color:var(--color-ink)] text-center mb-12 tracking-[-0.02em]">
            Что анализирует AI
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {[
              { icon: '🧩', title: 'Навыки', desc: 'Какие технологии и компетенции выделены, насколько они актуальны на рынке.' },
              { icon: '📊', title: 'Грейд', desc: 'Определяем Junior / Middle / Senior на основе опыта и формулировок.' },
              { icon: '✅', title: 'Сильные стороны', desc: 'Что выделяет вас на фоне других кандидатов с похожим бэкграундом.' },
              { icon: '📈', title: 'Зоны роста', desc: 'Чего не хватает для следующего уровня или для попадания в целевые компании.' },
              { icon: '⚠️', title: 'Риски для найма', desc: 'Формулировки и пробелы, которые рекрутер воспринимает как тревожные сигналы.' },
              { icon: '🔍', title: 'Ключевые слова', desc: 'Совпадение с языком вакансий — важно для ATS-систем автоматической фильтрации.' },
            ].map(({ icon, title, desc }) => (
              <div
                key={title}
                className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6"
              >
                <span className="text-3xl mb-3 block">{icon}</span>
                <h3 className="text-[length:var(--text-lg)] font-semibold text-[color:var(--color-ink)] mb-2">{title}</h3>
                <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">{desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Mock карточка анализа */}
        <div className="max-w-[780px] mx-auto px-6 py-8">
          <h2 className="text-[length:var(--text-3xl)] font-bold text-[color:var(--color-ink)] mb-8 tracking-[-0.02em]">
            Пример карточки анализа
          </h2>
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6 space-y-5">
            <div className="flex items-center justify-between flex-wrap gap-3">
              <div>
                <p className="text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)] uppercase tracking-widest mb-1">Кандидат</p>
                <p className="text-[length:var(--text-xl)] font-bold text-[color:var(--color-ink)]">Иван Петров — Frontend Developer</p>
              </div>
              <span className="px-4 py-1.5 rounded-full bg-[var(--color-success-subtle)] text-[color:var(--color-success)] text-[length:var(--text-sm)] font-semibold">
                Middle+
              </span>
            </div>
            <hr className="border-[var(--color-border)]" />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <p className="text-[length:var(--text-xs)] font-semibold uppercase tracking-wider text-[color:var(--color-ink-secondary)] mb-2">Сильные стороны</p>
                <ul className="space-y-1.5">
                  {['React + TypeScript — продвинутый уровень', 'Опыт с монорепо и CI/CD', 'Упоминание метрик в достижениях'].map((s) => (
                    <li key={s} className="flex gap-2 text-[length:var(--text-sm)] text-[color:var(--color-ink)]">
                      <span className="text-[color:var(--color-success)]">✓</span> {s}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="text-[length:var(--text-xs)] font-semibold uppercase tracking-wider text-[color:var(--color-ink-secondary)] mb-2">Зоны роста</p>
                <ul className="space-y-1.5">
                  {['Нет упоминания тестирования', 'Soft-skills не отражены', 'Пробел в 2022 не объяснён'].map((s) => (
                    <li key={s} className="flex gap-2 text-[length:var(--text-sm)] text-[color:var(--color-ink)]">
                      <span className="text-[color:var(--color-warning)]">!</span> {s}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="rounded-[var(--radius-lg)] bg-[var(--color-danger-subtle)] border border-[var(--color-border)] p-4">
              <p className="text-[length:var(--text-xs)] font-semibold uppercase tracking-wider text-[color:var(--color-danger)] mb-1">Риск для найма</p>
              <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink)]">«Участвовал в разработке» — пассивные формулировки снижают доверие рекрутера.</p>
            </div>
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
