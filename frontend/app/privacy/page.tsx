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
            Как обрабатываются данные
          </h1>
          <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)]">
            Последнее обновление: 24 апреля 2026 г.
          </p>
        </div>

        {/* Контент */}
        <div className="max-w-[780px] mx-auto px-6 pb-20 space-y-6">
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Статус проекта
            </h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              Это персональный демонстрационный проект, опубликованный автором в ознакомительных
              и портфолио-целях. За сервисом не стоит юридическое лицо или индивидуальный
              предприниматель. Сервис не оказывает коммерческих услуг, не взимает плату и не
              заключает договоров с пользователями.
            </p>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Что сервис НЕ хранит
            </h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)] mb-3">
              При загрузке резюме сервис автоматически обезличивает текст перед любой дальнейшей
              обработкой. После анализа НЕ сохраняются:
            </p>
            <ul className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)] space-y-1 list-disc pl-6">
              <li>имена и фамилии, указанные в резюме</li>
              <li>номера телефонов</li>
              <li>ссылки на профили в социальных сетях</li>
              <li>даты рождения</li>
              <li>исходный файл резюме (удаляется сразу после анализа)</li>
              <li>исходный текст резюме (не помещается в базу данных)</li>
            </ul>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)] mt-3">
              Исходное название загруженного файла также не сохраняется — в базе остаётся
              только тип (PDF/DOCX).
            </p>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Что сохраняется
            </h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)] mb-3">
              Только необходимый для работы сервиса минимум:
            </p>
            <ul className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)] space-y-1 list-disc pl-6">
              <li>email — для входа в учётную запись</li>
              <li>хеш пароля (bcrypt) — пароль в открытом виде не сохраняется</li>
              <li>
                обезличенный профиль резюме — должность, грейд, навыки, домены, краткое описание
                опыта. Без имён и контактов.
              </li>
              <li>
                предпочтения — формат работы, желаемые должности, зарплатная вилка, город (на
                уровне названия)
              </li>
              <li>
                обратная связь по вакансиям — лайки/дизлайки, статус отклика, заметки
                пользователя
              </li>
            </ul>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Передача обезличенного текста во внешний LLM
            </h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              Для структурного анализа и векторизации обезличенный текст резюме передаётся в
              OpenAI API (США). До передачи из текста автоматически удалены имена, email,
              телефоны, ссылки на соцсети, даты рождения. В OpenAI не передаются email учётной
              записи, пароль, обратная связь по вакансиям и история откликов.
            </p>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Доступ к внешним сервисам
            </h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              Для подбора вакансий сервис обращается к публичному API hh.ru. Данные пользователя
              в этих запросах не передаются — отправляется только поисковый запрос, сформированный
              из обезличенного профиля резюме.
            </p>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Меры защиты
            </h2>
            <ul className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)] space-y-1 list-disc pl-6">
              <li>HTTPS для передачи данных между браузером и сервером</li>
              <li>JWT-токены с истечением срока, подтверждение входа через email</li>
              <li>bcrypt для хеширования паролей</li>
              <li>Ограничение частоты запросов на эндпоинты авторизации</li>
              <li>Отдельный фильтр от prompt-injection на входе в LLM</li>
            </ul>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Удаление учётной записи и данных
            </h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              Каждый пользователь может запросить удаление учётной записи и всех связанных с ней
              данных, написав письмо на{' '}
              <a
                href="mailto:artyom.khiryov@yandex.ru"
                className="text-[color:var(--color-accent)] hover:underline"
              >
                artyom.khiryov@yandex.ru
              </a>{' '}
              с адреса, указанного при регистрации. Удаление выполняется в разумный срок, обычно
              в течение нескольких дней. Удаление конкретного резюме из учётной записи доступно
              в интерфейсе сервиса.
            </p>
          </div>

          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 shadow-[var(--shadow-sm)] p-6">
            <h2 className="text-[length:var(--text-lg)] font-bold text-[color:var(--color-ink)] mb-3">
              Контакт
            </h2>
            <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-relaxed)]">
              По любым вопросам об обработке данных —{' '}
              <a
                href="mailto:artyom.khiryov@yandex.ru"
                className="text-[color:var(--color-accent)] hover:underline"
              >
                artyom.khiryov@yandex.ru
              </a>
              . Исходный код сервиса открыт и доступен на{' '}
              <a
                href="https://github.com/fat32al1ty/HR-assist"
                target="_blank"
                rel="noreferrer"
                className="text-[color:var(--color-accent)] hover:underline"
              >
                GitHub
              </a>
              .
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}
