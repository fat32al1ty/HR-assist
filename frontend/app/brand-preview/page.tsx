import Image from 'next/image';
import Link from 'next/link';

const BRAND_ASSETS = {
  icon32: '/brand-preview-assets/aijobmatch-variant2-icon-32.png',
  icon64: '/brand-preview-assets/aijobmatch-variant2-icon-64.png',
  icon128: '/brand-preview-assets/aijobmatch-variant2-icon-128.png',
  icon256: '/brand-preview-assets/aijobmatch-variant2-icon-256.png',
  icon512: '/brand-preview-assets/aijobmatch-variant2-icon-512.png',
  logo320: '/brand-preview-assets/aijobmatch-variant2-logo-320w.png',
  logo640: '/brand-preview-assets/aijobmatch-variant2-logo-640w.png',
  logo1280: '/brand-preview-assets/aijobmatch-variant2-logo-1280w.png',
  logoTransparent: '/brand-preview-assets/aijobmatch-variant2-logo-transparent.png',
  favicon: '/brand-preview-assets/aijobmatch-variant2-favicon.ico',
} as const;

const HERO_POINTS: ReadonlyArray<readonly [string, string]> = [
  [
    'Релевантный подбор вместо шума',
    'AI учитывает стек, опыт, домен и контекст резюме, чтобы не показывать нерелевантные роли.',
  ],
  [
    'Прозрачный fit/gap-анализ',
    'По каждой вакансии видно: что совпало, где пробелы и насколько реалистичен следующий шаг.',
  ],
  [
    'Сопровождение всей воронки',
    'Отклики, AI cover letter и статусы в одной рабочей панели без ручных таблиц.',
  ],
  [
    'Качество растет с каждым циклом',
    'Feedback loop учитывает отклики, отказы и действия кандидата для следующего ранжирования.',
  ],
];

const LOGO_RULES = [
  'Primary логотип: aijobmatch-variant2-logo-1280w.png.',
  'Иконка продукта: aijobmatch-variant2-icon-256.png.',
  'Favicon: aijobmatch-variant2-favicon.ico.',
  'Для более узких контейнеров можно использовать aijobmatch-variant2-logo-640w.png.',
] as const;

const LANDING_BLOCKS = [
  {
    title: 'Позиционирование',
    body: 'AI-powered карьерный ассистент для соискателя: от анализа профиля до результата в откликах.',
  },
  {
    title: 'Главное обещание',
    body: 'Не просто список вакансий, а подбор с оценкой шансов и объяснимой логикой.',
  },
  {
    title: 'Ключевая ценность',
    body: 'Соискатель понимает, куда стоит откликаться сейчас, а что лучше усилить в профиле.',
  },
] as const;

function LogoStrip() {
  return (
    <div className="flex items-center gap-3">
      <Image
        src={BRAND_ASSETS.icon64}
        alt="AIJobMatch icon"
        width={40}
        height={40}
        className="rounded-[10px] shadow-[var(--shadow-sm)]"
      />
      <div className="flex flex-col">
        <span className="text-[length:var(--text-xl)] font-bold leading-none text-[color:var(--color-ink)]">
          AIJobMatch
        </span>
        <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]">aijobmatch.ru</span>
      </div>
    </div>
  );
}

export default function BrandPreviewPage() {
  return (
    <main className="page">
      <section className="main">
        <div className="max-w-[1220px] mx-auto px-6 pt-12 pb-16">
          <div className="rounded-[28px] border border-[var(--color-border)] bg-[radial-gradient(1200px_520px_at_20%_-5%,rgba(59,130,246,0.14),transparent)] shadow-[var(--shadow-sm)]">
            <div className="p-8 md:p-10 lg:p-12">
              <span className="inline-flex items-center rounded-full border border-[var(--color-border)] bg-white px-3 py-1 text-[length:var(--text-xs)] font-bold uppercase tracking-[0.08em] text-[color:var(--color-ink-secondary)]">
                Brand preview · draft
              </span>

              <div className="mt-6 grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr] gap-8 lg:gap-10">
                <div>
                  <LogoStrip />
                  <span className="mt-6 inline-flex rounded-full border border-[var(--color-border)] bg-white px-3 py-1 text-[length:var(--text-xs)] font-bold uppercase tracking-[0.08em] text-[color:var(--color-ink-secondary)]">
                    AI career assistant for job seekers
                  </span>
                  <h1 className="mt-4 max-w-[720px] text-[length:var(--text-display)] leading-[var(--leading-tight)] tracking-[-0.035em] font-bold text-[color:var(--color-ink)]">
                    AI подбирает релевантные вакансии и честно показывает,{' '}
                    <span className="text-[color:var(--color-accent)]">куда реально стоит откликаться</span>
                  </h1>
                  <p className="mt-4 max-w-[700px] text-[length:var(--text-lg)] leading-[var(--leading-relaxed)] text-[color:var(--color-ink-secondary)]">
                    От анализа резюме и рыночного профиля до explainable fit/gap, AI cover letter и управляемой
                    воронки откликов.
                  </p>

                  <ul className="mt-7 grid gap-3 max-w-[760px]">
                    {HERO_POINTS.map(([title, body]) => (
                      <li key={title} className="flex gap-3">
                        <span className="mt-[3px] inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-subtle)] text-[color:var(--color-accent)] text-[length:var(--text-xs)] font-bold">
                          ✓
                        </span>
                        <div>
                          <p className="font-semibold text-[length:var(--text-sm)] text-[color:var(--color-ink)]">{title}</p>
                          <p className="text-[length:var(--text-sm)] leading-[var(--leading-snug)] text-[color:var(--color-ink-secondary)]">
                            {body}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>

                  <div className="mt-7 flex flex-wrap gap-3">
                    <button
                      type="button"
                      disabled
                      className="rounded-[var(--radius-md)] bg-[var(--color-accent)] px-4 py-2.5 text-[color:var(--color-on-accent)] font-semibold opacity-90 cursor-not-allowed"
                    >
                      Загрузить резюме
                    </button>
                    <button
                      type="button"
                      disabled
                      className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-4 py-2.5 text-[color:var(--color-ink-secondary)] font-semibold cursor-not-allowed"
                    >
                      Посмотреть demo flow
                    </button>
                  </div>
                </div>

                <div className="rounded-[24px] border border-[var(--color-border)] bg-white/80 p-6 md:p-7 shadow-[var(--shadow-sm)] self-start">
                  <h2 className="text-[length:var(--text-3xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
                    Вход в кабинет
                  </h2>
                  <p className="mt-1 text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)]">
                    Войдите, чтобы получить подбор вакансий под ваш профиль
                  </p>
                  <div className="mt-5 flex flex-col gap-3">
                    <input placeholder="Email" disabled />
                    <input type="password" placeholder="Пароль" disabled />
                    <button
                      type="button"
                      disabled
                      className="rounded-[var(--radius-md)] bg-[var(--color-accent)] px-4 py-2.5 text-[color:var(--color-on-accent)] font-semibold opacity-90 cursor-not-allowed"
                    >
                      Войти
                    </button>
                    <button
                      type="button"
                      disabled
                      className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-4 py-2.5 text-[color:var(--color-ink-secondary)] font-semibold cursor-not-allowed"
                    >
                      Нет аккаунта? Зарегистрироваться
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-8 grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-5">
            <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 p-6 shadow-[var(--shadow-sm)]">
              <h2 className="text-[length:var(--text-2xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
                Логотип из вашего site pack
              </h2>
              <p className="mt-2 text-[length:var(--text-sm)] leading-[var(--leading-snug)] text-[color:var(--color-ink-secondary)]">
                Подключен реальный logo pack `variant2` из папки, которую вы прислали.
              </p>

              <div className="mt-5 rounded-[18px] border border-[var(--color-border)] bg-[linear-gradient(135deg,#dbeafe_0%,#eff6ff_40%,#ffffff_100%)] p-6">
                <Image
                  src={BRAND_ASSETS.logo1280}
                  alt="AIJobMatch logo variant2"
                  width={1280}
                  height={384}
                  className="h-auto w-full max-w-[560px]"
                  priority
                />
                <div className="mt-5 flex items-center gap-3">
                  <Image src={BRAND_ASSETS.icon128} alt="AIJobMatch icon 128" width={34} height={34} className="rounded-[8px]" />
                  <Image src={BRAND_ASSETS.icon64} alt="AIJobMatch icon 64" width={22} height={22} className="rounded-[6px]" />
                  <Image src={BRAND_ASSETS.icon32} alt="AIJobMatch icon 32" width={16} height={16} className="rounded-[4px]" />
                </div>
              </div>
            </div>

            <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 p-6 shadow-[var(--shadow-sm)]">
              <h2 className="text-[length:var(--text-2xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
                Правила применения
              </h2>
              <ul className="mt-4 space-y-3 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                {LOGO_RULES.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="text-[color:var(--color-accent)]">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-5 rounded-[14px] border border-[var(--color-accent)]/35 bg-[var(--color-accent-subtle)] p-4">
                <p className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
                  Рекомендуем зафиксировать:
                </p>
                <p className="mt-1 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                  логотип `variant2` + доменный wordmark как единый бренд для `aijobmatch.ru`.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-8 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 p-6 shadow-[var(--shadow-sm)]">
            <h2 className="text-[length:var(--text-2xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
              Лендинг: финальная подача
            </h2>
            <div className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-4">
              {LANDING_BLOCKS.map(({ title, body }) => (
                <div
                  key={title}
                  className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white p-5"
                >
                  <h3 className="font-semibold text-[length:var(--text-base)] text-[color:var(--color-ink)]">{title}</h3>
                  <p className="mt-2 text-[length:var(--text-sm)] leading-[var(--leading-snug)] text-[color:var(--color-ink-secondary)]">
                    {body}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-8 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 p-6 shadow-[var(--shadow-sm)]">
            <h2 className="text-[length:var(--text-2xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
              Что изменили относительно текущей боевой
            </h2>
            <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white p-5">
                <p className="text-[length:var(--text-xs)] font-bold uppercase tracking-[0.08em] text-[color:var(--color-ink-muted)]">
                  Было
                </p>
                <ul className="mt-3 space-y-2 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                  <li>HR-консультант как общее позиционирование.</li>
                  <li>Слабая связка бренда с доменом aijobmatch.</li>
                  <li>Меньше акцента на explainability и feedback loop.</li>
                </ul>
              </div>
              <div className="rounded-[var(--radius-md)] border border-[var(--color-accent)]/35 bg-[var(--color-accent-subtle)] p-5">
                <p className="text-[length:var(--text-xs)] font-bold uppercase tracking-[0.08em] text-[color:var(--color-accent)]">
                  Стало
                </p>
                <ul className="mt-3 space-y-2 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                  <li>AIJobMatch как единый продуктовый бренд.</li>
                  <li>Реальный вариант2-логотип из вашего пака на hero/бренд-блоке.</li>
                  <li>Четкая формула ценности: match + шансы + объяснение + цикл обучения.</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="mt-8 mb-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 p-6 shadow-[var(--shadow-sm)]">
            <h2 className="text-[length:var(--text-xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
              Что дальше перед переносом в боевую
            </h2>
            <ol className="mt-4 list-decimal list-inside space-y-2 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
              <li>Утвердить variant2 как основной логотип бренда.</li>
              <li>Уточнить подпись `HR ASSIST` в wordmark (оставляем или убираем в следующем экспорте).</li>
              <li>Перенести изменения в боевую страницу отдельным шагом.</li>
            </ol>
            <Link
              href="/"
              className="mt-5 inline-flex items-center gap-1 text-[length:var(--text-sm)] font-semibold text-[color:var(--color-accent)] hover:underline"
            >
              ← Вернуться на основной сайт
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
