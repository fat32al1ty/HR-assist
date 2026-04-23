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
            HR консультант — персональный AI-проект по анализу резюме и подбору вакансий. Демонстрационный, не коммерческий.
          </p>
        </div>

        {/* Статус */}
        <div className="max-w-[780px] mx-auto px-6 py-8">
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">Статус</h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              Проект ведёт один автор — как открытое портфолио. Юридического лица или ИП за сервисом нет, плата не взимается, договор с пользователем не заключается. Код открыт на GitHub, сервис разворачивается локально через Docker. Публичный экземпляр работает в демонстрационном режиме.
            </p>
          </div>
        </div>

        {/* Идея */}
        <div className="max-w-[780px] mx-auto px-6 py-12">
          <h2 className="text-[length:var(--text-3xl)] font-bold text-[color:var(--color-ink)] mb-6 tracking-[-0.02em]">Идея</h2>
          <div className="space-y-4 text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
            <p>
              Поиск работы через типовые job-борды — это сотни вакансий, ноль объяснений, почему кандидат подходит, и непрозрачный ранжир. Идея проекта — собрать end-to-end AI-систему, которая читает резюме, извлекает структурный профиль, семантически матчит вакансии и объясняет, каких навыков не хватает.
            </p>
            <p>
              Это инженерный эксперимент: посмотреть, насколько далеко можно продвинуть качество подбора с помощью векторного поиска, многоступенчатого ранкера, ESCO-классификации ролей и evaluation-харнесса. Параллельно — собрать приличную внешнюю обвязку вокруг auth, приватности и разработческой петли.
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
