export default function TermsPage() {
  return (
    <main className="page">
      <section className="main">
        {/* Hero */}
        <div className="max-w-[780px] mx-auto text-center py-20 px-6">
          <span className="inline-block mb-4 px-4 py-1.5 rounded-full border border-[var(--color-border)] bg-white/70 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] font-medium">
            Правовое
          </span>
          <h1 className="text-[length:var(--text-display)] font-bold tracking-[-0.03em] leading-[var(--leading-tight)] text-[color:var(--color-ink)] mb-4">
            Условия использования
          </h1>
          <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)]">
            Последнее обновление: 23 апреля 2026 г.
          </p>
        </div>

        {/* Контент */}
        <div className="max-w-[780px] mx-auto px-6 pb-20 space-y-8">
          {[
            {
              title: '1. Что такое сервис',
              body: 'HR консультант — это AI-инструмент для соискателей, предназначенный для анализа резюме, подбора вакансий и отслеживания откликов. Сервис не является рекрутинговым агентством и не гарантирует трудоустройство.',
            },
            {
              title: '2. Регистрация',
              body: 'Для использования сервиса необходима регистрация с действующим адресом электронной почты. Вы несёте ответственность за сохранность учётных данных. Один человек — один аккаунт.',
            },
            {
              title: '3. Запрещённые действия',
              body: 'Запрещается: использовать сервис в автоматическом режиме (боты, скрипты) без письменного согласия; загружать чужие резюме без согласия их авторов; пытаться получить несанкционированный доступ к данным других пользователей; использовать сервис в целях, противоречащих законодательству.',
            },
            {
              title: '4. Ограничение ответственности',
              body: 'Сервис предоставляется «как есть». Мы не несём ответственности за решения работодателей, за точность AI-анализа в каждом конкретном случае, за перебои в работе сторонних сервисов (OpenAI, Qdrant). Максимальная ответственность сервиса ограничена суммой оплаченной подписки за последний месяц.',
            },
            {
              title: '5. Изменения условий',
              body: 'Мы вправе изменять настоящие условия. О существенных изменениях уведомляем по email не менее чем за 14 дней. Продолжение использования сервиса после уведомления означает согласие с новыми условиями.',
            },
          ].map(({ title, body }) => (
            <div
              key={title}
              className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6"
            >
              <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">{title}</h2>
              <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">{body}</p>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
