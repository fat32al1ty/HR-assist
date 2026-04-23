export default function PrivacyPage() {
  return (
    <main className="page">
      <section className="main">
        {/* Hero */}
        <div className="max-w-[780px] mx-auto text-center py-20 px-6">
          <span className="inline-block mb-4 px-4 py-1.5 rounded-full border border-[var(--color-border)] bg-white/70 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] font-medium">
            Правовое
          </span>
          <h1 className="text-[length:var(--text-display)] font-bold tracking-[-0.03em] leading-[var(--leading-tight)] text-[color:var(--color-ink)] mb-4">
            Политика конфиденциальности
          </h1>
          <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)]">
            Последнее обновление: 23 апреля 2026 г.
          </p>
        </div>

        {/* Контент */}
        <div className="max-w-[780px] mx-auto px-6 pb-20 space-y-8">
          {[
            {
              title: '1. Что мы собираем',
              body: 'Мы собираем только те данные, которые необходимы для работы сервиса: содержимое вашего резюме (загружаемый файл или вставленный текст), адрес электронной почты при регистрации, а также технические данные об использовании сервиса (cookies сессии, анонимные аналитические события).',
            },
            {
              title: '2. Как мы используем данные',
              body: 'Данные резюме используются исключительно для AI-анализа и подбора вакансий внутри сервиса. Email используется для аутентификации и уведомлений, связанных с вашим аккаунтом. Мы не используем ваши данные для обучения публичных моделей без явного согласия.',
            },
            {
              title: '3. Передача третьим лицам',
              body: 'Мы не продаём, не сдаём в аренду и не передаём ваши персональные данные третьим лицам в коммерческих целях. Техническая обработка данных осуществляется через OpenAI API (анализ текста) и Qdrant (векторная база). Оба провайдера действуют в рамках Data Processing Agreements.',
            },
            {
              title: '4. Хранение и безопасность',
              body: 'Данные хранятся на защищённых серверах. Резюме не раскрывается другим пользователям. Мы применяем шифрование данных в транзите (HTTPS) и в покое.',
            },
            {
              title: '5. Удаление данных',
              body: 'Вы можете запросить полное удаление вашего аккаунта и всех связанных данных, написав на artyom.khiryov@yandex.ru. Данные удаляются в течение 30 дней с момента запроса.',
            },
            {
              title: '6. Контакт DPO',
              body: 'По вопросам защиты персональных данных обращайтесь к ответственному за обработку данных: artyom.khiryov@yandex.ru.',
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
