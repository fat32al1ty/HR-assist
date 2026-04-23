export default function AboutPage() {
  return (
    <main className="page">
      <section className="main">
        {/* Hero */}
        <div className="max-w-[780px] mx-auto text-center py-20 px-6">
          <span className="inline-block mb-4 px-4 py-1.5 rounded-full border border-[var(--color-border)] bg-white/70 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] font-medium">
            О проекте
          </span>
          <h1 className="text-[length:var(--text-display)] font-bold tracking-[-0.03em] leading-[var(--leading-tight)] text-[color:var(--color-ink)] mb-6">
            Мы помогаем находить<br />работу быстрее и осознаннее
          </h1>
          <p className="text-[length:var(--text-xl)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
            HR консультант — AI-ассистент для соискателей. Не агрегатор, не рекрутинговое агентство. Инструмент на вашей стороне.
          </p>
        </div>

        {/* Миссия */}
        <div className="max-w-[780px] mx-auto px-6 py-12">
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-8">
            <h2 className="text-[length:var(--text-2xl)] font-bold text-[color:var(--color-ink)] mb-4 tracking-[-0.02em]">Миссия</h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              Помочь каждому соискателю находить работу быстрее и осознаннее — без спама, без интуитивных откликов наугад и без переплаты за Premium-подписки, которые не объясняют, почему вакансия подходит именно вам.
            </p>
          </div>
        </div>

        {/* История */}
        <div className="max-w-[780px] mx-auto px-6 py-12">
          <h2 className="text-[length:var(--text-3xl)] font-bold text-[color:var(--color-ink)] mb-6 tracking-[-0.02em]">Как появился проект</h2>
          <div className="space-y-4 text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
            <p>
              Всё началось с личного опыта: поиск работы через hh.ru — это сотни вакансий-спама, ноль объяснений, почему ты подходишь или нет, и Premium-подписка за 2 500 ₽ в месяц, которая просто поднимает отклик в ленте.
            </p>
            <p>
              Мы задались вопросом: а что, если AI мог бы читать резюме так же, как опытный рекрутер, и честно говорить — вот твои сильные стороны, вот что тебя тормозит, вот вакансии, где ты реально конкурентоспособен?
            </p>
            <p>
              Так появился HR консультант. Инструмент, который работает на соискателя, а не на площадку.
            </p>
          </div>
        </div>

        {/* Что отличает */}
        <div className="max-w-[1100px] mx-auto px-6 py-12">
          <h2 className="text-[length:var(--text-3xl)] font-bold text-[color:var(--color-ink)] text-center mb-10 tracking-[-0.02em]">
            Что нас отличает
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                icon: '🔍',
                title: 'Прозрачность',
                desc: 'Объясняем каждый матч. Вы знаете, почему вакансия подходит, ещё до того как откликнетесь.',
              },
              {
                icon: '🎯',
                title: 'Честность',
                desc: 'Говорим, когда вы не подходите — и объясняем, что изменить. Не льём мотивацию без смысла.',
              },
              {
                icon: '⚡',
                title: 'Скорость',
                desc: 'Анализ резюме и подбор вакансий — минуты, не дни. Сопроводительное — одна кнопка.',
              },
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

      </section>
    </main>
  );
}
