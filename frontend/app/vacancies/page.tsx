import Link from 'next/link';

export default function VacanciesPage() {
  return (
    <main className="page">
      <section className="main">
        {/* Hero */}
        <div className="max-w-[780px] mx-auto text-center py-20 px-6">
          <span className="inline-block mb-4 px-4 py-1.5 rounded-full border border-[var(--color-border)] bg-white/70 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] font-medium">
            Подбор вакансий
          </span>
          <h1 className="text-[length:var(--text-display)] font-bold tracking-[-0.03em] leading-[var(--leading-tight)] text-[color:var(--color-ink)] mb-6">
            Каждая вакансия — с аргументом,<br />почему именно вам подходит
          </h1>
          <p className="text-[length:var(--text-xl)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)] mb-10">
            AI анализирует ваше резюме и находит вакансии с реальным совпадением — не по ключевым словам, а по смыслу.
          </p>
          <Link
            href="/"
            className="inline-block px-8 py-3.5 rounded-[var(--radius-lg)] bg-[var(--color-accent)] text-[color:var(--color-on-accent)] font-semibold text-[length:var(--text-base)] shadow-[var(--shadow-sm)] transition-opacity hover:opacity-90"
          >
            Начать — это бесплатно
          </Link>
        </div>

        {/* 3 шага */}
        <div className="max-w-[1100px] mx-auto px-6 py-16">
          <h2 className="text-[length:var(--text-3xl)] font-bold text-[color:var(--color-ink)] text-center mb-12 tracking-[-0.02em]">
            Как это работает
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                step: '01',
                title: 'Загрузите резюме',
                desc: 'Загрузите PDF или вставьте текст. AI считывает навыки, опыт, стек и уровень — без анкет и форм.',
              },
              {
                step: '02',
                title: 'Получите список',
                desc: 'Система сопоставляет вас с тысячами вакансий и возвращает те, где совпадение реально высокое.',
              },
              {
                step: '03',
                title: 'Поймите почему',
                desc: 'Каждая вакансия сопровождается объяснением: что совпало, что нет, стоит ли откликаться.',
              },
            ].map(({ step, title, desc }) => (
              <div
                key={step}
                className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6"
              >
                <span className="text-[length:var(--text-3xl)] font-black text-[color:var(--color-accent)] opacity-30 leading-none block mb-4">
                  {step}
                </span>
                <h3 className="text-[length:var(--text-lg)] font-semibold text-[color:var(--color-ink)] mb-2">{title}</h3>
                <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">{desc}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Почему не просто поиск */}
        <div className="max-w-[780px] mx-auto px-6 py-16">
          <h2 className="text-[length:var(--text-3xl)] font-bold text-[color:var(--color-ink)] mb-8 tracking-[-0.02em]">
            Почему не просто поиск на hh.ru
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { label: 'hh.ru', text: 'Сотни вакансий по ключевым словам, 90% — спам' },
              { label: 'HR консультант', text: 'Только релевантные позиции с объяснением матча' },
              { label: 'hh.ru', text: 'Premium не объясняет, почему вакансия подходит' },
              { label: 'HR консультант', text: 'Каждая вакансия — с аргументом, почему именно вам' },
              { label: 'hh.ru', text: 'Откликаетесь вслепую, ждёте неделями' },
              { label: 'HR консультант', text: 'Видите процент совпадения до отклика' },
            ].map(({ label, text }, i) => (
              <div
                key={i}
                className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-4 flex gap-3 items-start"
              >
                <span
                  className={`shrink-0 mt-0.5 text-[length:var(--text-xs)] font-bold px-2 py-0.5 rounded-full ${
                    label === 'hh.ru'
                      ? 'bg-[var(--color-danger-subtle)] text-[color:var(--color-danger)]'
                      : 'bg-[var(--color-success-subtle)] text-[color:var(--color-success)]'
                  }`}
                >
                  {label}
                </span>
                <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink)] leading-[var(--leading-relaxed)]">{text}</p>
              </div>
            ))}
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
