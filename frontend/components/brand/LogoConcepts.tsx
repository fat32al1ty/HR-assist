/**
 * LogoConcepts — 10 hand-crafted SVG logo variants for AI JobMatch.
 * Each concept: primary mark, horizontal lockup, 32px favicon preview.
 * Light + dark surface previews side by side.
 * No raster images, no external deps, no raw hex — uses currentColor +
 * CSS custom property tokens throughout.
 *
 * Ownership: designer agent. Do NOT add logic, state, or API calls here.
 */

const concepts = [
  {
    id: 1,
    label: 'Bracket-A',
    description: 'Квадратные скобки образуют стилизованную «A» — код как контекст, краткость как принцип.',
    mark: (
      <svg viewBox="0 0 40 40" aria-label="AI JobMatch mark — Bracket A" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Left bracket */}
        <path d="M14 8 L8 8 L8 32 L14 32" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
        {/* Right bracket */}
        <path d="M26 8 L32 8 L32 32 L26 32" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
        {/* Middle crossbar — the "A" bar */}
        <path d="M11 20 L29 20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
        {/* Accent dot */}
        <circle cx="20" cy="12" r="2.5" fill="currentColor"/>
      </svg>
    ),
    faviconMark: (
      <svg viewBox="0 0 32 32" aria-label="favicon" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M10 6 L5 6 L5 26 L10 26" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M22 6 L27 6 L27 26 L22 26" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M8 16 L24 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <circle cx="16" cy="10" r="2" fill="currentColor"/>
      </svg>
    ),
  },
  {
    id: 2,
    label: 'Signal-dot',
    description: 'Три нарастающие полосы с точкой-акцентом — сигнал, рост, точность попадания.',
    mark: (
      <svg viewBox="0 0 40 40" aria-label="AI JobMatch mark — Signal dot" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Three bars, ascending */}
        <rect x="6" y="26" width="6" height="8" rx="1.5" fill="currentColor" opacity="0.35"/>
        <rect x="17" y="19" width="6" height="15" rx="1.5" fill="currentColor" opacity="0.65"/>
        <rect x="28" y="10" width="6" height="24" rx="1.5" fill="currentColor"/>
        {/* Accent dot top-right */}
        <circle cx="34" cy="7" r="3" fill="currentColor"/>
      </svg>
    ),
    faviconMark: (
      <svg viewBox="0 0 32 32" aria-label="favicon" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="4" y="21" width="5" height="7" rx="1" fill="currentColor" opacity="0.35"/>
        <rect x="13" y="15" width="5" height="13" rx="1" fill="currentColor" opacity="0.65"/>
        <rect x="22" y="8" width="5" height="20" rx="1" fill="currentColor"/>
        <circle cx="27" cy="5.5" r="2.5" fill="currentColor"/>
      </svg>
    ),
  },
  {
    id: 3,
    label: 'Match-square',
    description: 'Два перекрывающихся квадрата с общей зоной — пересечение кандидата и вакансии.',
    mark: (
      <svg viewBox="0 0 40 40" aria-label="AI JobMatch mark — Match square" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Left square */}
        <rect x="4" y="10" width="20" height="20" rx="3" stroke="currentColor" strokeWidth="2.5" fill="none"/>
        {/* Right square — overlapping, filled accent zone */}
        <rect x="16" y="10" width="20" height="20" rx="3" fill="currentColor" opacity="0.15" stroke="currentColor" strokeWidth="2.5"/>
        {/* Overlap fill */}
        <rect x="16" y="10" width="8" height="20" rx="1" fill="currentColor" opacity="0.3"/>
      </svg>
    ),
    faviconMark: (
      <svg viewBox="0 0 32 32" aria-label="favicon" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="3" y="8" width="16" height="16" rx="2.5" stroke="currentColor" strokeWidth="2" fill="none"/>
        <rect x="13" y="8" width="16" height="16" rx="2.5" fill="currentColor" opacity="0.15" stroke="currentColor" strokeWidth="2"/>
        <rect x="13" y="8" width="6" height="16" rx="1" fill="currentColor" opacity="0.35"/>
      </svg>
    ),
  },
  {
    id: 4,
    label: 'Arrow-target',
    description: 'Стрелка, входящая в квадрат — прямой вектор от анализа к результату, без лишнего.',
    mark: (
      <svg viewBox="0 0 40 40" aria-label="AI JobMatch mark — Arrow target" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Square frame */}
        <rect x="14" y="10" width="22" height="22" rx="3.5" stroke="currentColor" strokeWidth="2.5"/>
        {/* Arrow shaft entering from left */}
        <path d="M4 21 L23 21" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
        {/* Arrow head */}
        <path d="M18 16 L25 21 L18 26" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
        {/* Center dot */}
        <circle cx="25" cy="21" r="2.5" fill="currentColor"/>
      </svg>
    ),
    faviconMark: (
      <svg viewBox="0 0 32 32" aria-label="favicon" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="12" y="8" width="17" height="17" rx="2.5" stroke="currentColor" strokeWidth="2"/>
        <path d="M3 16.5 L19 16.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <path d="M15 12 L21 16.5 L15 21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      </svg>
    ),
  },
  {
    id: 5,
    label: 'AJ-monogram',
    description: 'Монограмма AJ в одном росчерке — буква J подчёркивает A снизу, два знака — одно имя.',
    mark: (
      <svg viewBox="0 0 40 40" aria-label="AI JobMatch mark — AJ monogram" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* A shape */}
        <path d="M8 32 L18 8 L28 32" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M12 24 L24 24" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
        {/* J descender from right leg of A */}
        <path d="M28 32 Q28 38 22 38 Q16 38 16 33" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" fill="none"/>
      </svg>
    ),
    faviconMark: (
      <svg viewBox="0 0 32 32" aria-label="favicon" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M6 26 L14 6 L22 26" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M9 19 L19 19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <path d="M22 26 Q22 31 17 31 Q12 31 12 27" stroke="currentColor" strokeWidth="2" strokeLinecap="round" fill="none"/>
      </svg>
    ),
  },
  {
    id: 6,
    label: 'Grid-spark',
    description: 'Сетка 3×3 с выделенной правой колонкой — данные, структура, выверенный выбор.',
    mark: (
      <svg viewBox="0 0 40 40" aria-label="AI JobMatch mark — Grid spark" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* 3×3 grid — left 2 columns muted */}
        {[0, 1, 2].map((row) =>
          [0, 1].map((col) => (
            <rect
              key={`${row}-${col}`}
              x={6 + col * 11}
              y={8 + row * 11}
              width="8"
              height="8"
              rx="1.5"
              fill="currentColor"
              opacity="0.25"
            />
          ))
        )}
        {/* Right column — accent, full opacity */}
        {[0, 1, 2].map((row) => (
          <rect
            key={`accent-${row}`}
            x={28}
            y={8 + row * 11}
            width="8"
            height="8"
            rx="1.5"
            fill="currentColor"
          />
        ))}
      </svg>
    ),
    faviconMark: (
      <svg viewBox="0 0 32 32" aria-label="favicon" fill="none" xmlns="http://www.w3.org/2000/svg">
        {[0, 1, 2].map((row) =>
          [0, 1].map((col) => (
            <rect
              key={`${row}-${col}`}
              x={4 + col * 9}
              y={6 + row * 9}
              width="6"
              height="6"
              rx="1"
              fill="currentColor"
              opacity="0.25"
            />
          ))
        )}
        {[0, 1, 2].map((row) => (
          <rect
            key={`a-${row}`}
            x={22}
            y={6 + row * 9}
            width="6"
            height="6"
            rx="1"
            fill="currentColor"
          />
        ))}
      </svg>
    ),
  },
  {
    id: 7,
    label: 'Slash-AI',
    description: 'Диагональная черта делит квадрат на две зоны — «до» и «после» AI-оценки.',
    mark: (
      <svg viewBox="0 0 40 40" aria-label="AI JobMatch mark — Slash AI" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Outer square */}
        <rect x="5" y="5" width="30" height="30" rx="5" stroke="currentColor" strokeWidth="2.5"/>
        {/* Diagonal slash */}
        <path d="M13 32 L27 8" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
        {/* Left zone label suggestion — dot */}
        <circle cx="9" cy="20" r="2" fill="currentColor" opacity="0.4"/>
        {/* Right zone — filled rectangle hint */}
        <rect x="29" y="17" width="3" height="6" rx="1" fill="currentColor"/>
      </svg>
    ),
    faviconMark: (
      <svg viewBox="0 0 32 32" aria-label="favicon" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="4" y="4" width="24" height="24" rx="4" stroke="currentColor" strokeWidth="2"/>
        <path d="M10 26 L22 6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    id: 8,
    label: 'Cursor-match',
    description: 'Курсор с пульсирующей точкой — момент выбора, точное попадание в нужную вакансию.',
    mark: (
      <svg viewBox="0 0 40 40" aria-label="AI JobMatch mark — Cursor match" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Cursor arrow */}
        <path d="M8 6 L8 28 L14 22 L18 32 L21 31 L17 21 L24 21 Z" fill="currentColor"/>
        {/* Accent ring at tip */}
        <circle cx="26" cy="14" r="7" stroke="currentColor" strokeWidth="2" opacity="0.3"/>
        <circle cx="26" cy="14" r="3" fill="currentColor"/>
      </svg>
    ),
    faviconMark: (
      <svg viewBox="0 0 32 32" aria-label="favicon" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M6 4 L6 22 L11 17 L14 25 L17 24 L14 16 L19 16 Z" fill="currentColor"/>
        <circle cx="21" cy="11" r="5.5" stroke="currentColor" strokeWidth="2" opacity="0.3"/>
        <circle cx="21" cy="11" r="2.5" fill="currentColor"/>
      </svg>
    ),
  },
  {
    id: 9,
    label: 'Stack-check',
    description: 'Горизонтальные полосы резюме с галочкой — структурированный профиль, подтверждённое соответствие.',
    mark: (
      <svg viewBox="0 0 40 40" aria-label="AI JobMatch mark — Stack check" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* Three document lines */}
        <line x1="6" y1="13" x2="24" y2="13" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
        <line x1="6" y1="20" x2="22" y2="20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
        <line x1="6" y1="27" x2="18" y2="27" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
        {/* Check mark — bold, bottom right */}
        <path d="M26 22 L30 27 L36 17" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
      </svg>
    ),
    faviconMark: (
      <svg viewBox="0 0 32 32" aria-label="favicon" fill="none" xmlns="http://www.w3.org/2000/svg">
        <line x1="5" y1="10" x2="19" y2="10" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <line x1="5" y1="16" x2="17" y2="16" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <line x1="5" y1="22" x2="14" y2="22" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        <path d="M20 17 L24 22 L29 13" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    id: 10,
    label: 'Vertex-M',
    description: 'Буква M, стилизованная под граф вершин и рёбер — match как соединение двух точек.',
    mark: (
      <svg viewBox="0 0 40 40" aria-label="AI JobMatch mark — Vertex M" fill="none" xmlns="http://www.w3.org/2000/svg">
        {/* M letterform as graph edges */}
        <path d="M6 30 L6 10 L20 22 L34 10 L34 30" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
        {/* Vertex circles */}
        <circle cx="6" cy="10" r="3" fill="currentColor"/>
        <circle cx="34" cy="10" r="3" fill="currentColor"/>
        <circle cx="20" cy="22" r="3" fill="currentColor"/>
        {/* Bottom dots smaller */}
        <circle cx="6" cy="30" r="2" fill="currentColor" opacity="0.45"/>
        <circle cx="34" cy="30" r="2" fill="currentColor" opacity="0.45"/>
      </svg>
    ),
    faviconMark: (
      <svg viewBox="0 0 32 32" aria-label="favicon" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M4 26 L4 8 L16 18 L28 8 L28 26" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" fill="none"/>
        <circle cx="4" cy="8" r="2.5" fill="currentColor"/>
        <circle cx="28" cy="8" r="2.5" fill="currentColor"/>
        <circle cx="16" cy="18" r="2.5" fill="currentColor"/>
      </svg>
    ),
  },
] as const;

// Wordmark rendered inline (no image dependency)
function Wordmark({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const sizes = {
    sm: 'text-sm font-bold tracking-[-0.02em]',
    md: 'text-xl font-bold tracking-[-0.025em]',
    lg: 'text-2xl font-bold tracking-[-0.03em]',
  };
  return (
    <span className={sizes[size]} style={{ color: 'var(--color-ink)', fontFamily: 'var(--font-body)' }}>
      <span style={{ color: 'var(--color-accent)' }}>AI</span>
      {' '}JobMatch
    </span>
  );
}

function LogoCard({
  concept,
}: {
  concept: (typeof concepts)[number];
}) {
  return (
    <div
      style={{
        border: '1px solid var(--color-border)',
        borderRadius: 'var(--radius-lg)',
        background: 'white',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--color-border)' }}>
        <span
          style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            letterSpacing: '0.08em',
            textTransform: 'uppercase' as const,
            color: 'var(--color-ink-secondary)',
          }}
        >
          #{concept.id} — {concept.label}
        </span>
      </div>

      {/* Two preview zones: light + dark */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
        {/* Light surface */}
        <div
          style={{
            padding: '24px 20px',
            background: '#f8fafc',
            borderRight: '1px solid var(--color-border)',
          }}
        >
          {/* Mark */}
          <div
            style={{
              width: 56,
              height: 56,
              color: 'var(--color-ink)',
            }}
          >
            {concept.mark}
          </div>

          {/* Horizontal lockup */}
          <div
            style={{
              marginTop: 16,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <div style={{ width: 28, height: 28, color: 'var(--color-ink)', flexShrink: 0 }}>
              {concept.mark}
            </div>
            <Wordmark size="md" />
          </div>

          {/* Favicon */}
          <div
            style={{
              marginTop: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                color: 'var(--color-ink)',
                background: 'white',
                borderRadius: 6,
                border: '1px solid var(--color-border)',
                padding: 3,
                flexShrink: 0,
              }}
            >
              {concept.faviconMark}
            </div>
            <span
              style={{
                fontSize: 'var(--text-xs)',
                color: 'var(--color-ink-muted)',
                fontWeight: 500,
              }}
            >
              32px favicon
            </span>
          </div>

          <p
            style={{
              fontSize: '10px',
              color: 'var(--color-ink-muted)',
              marginTop: 6,
              textTransform: 'uppercase' as const,
              letterSpacing: '0.06em',
              fontWeight: 600,
            }}
          >
            светлый фон
          </p>
        </div>

        {/* Dark surface */}
        <div
          style={{
            padding: '24px 20px',
            background: '#0f172a',
          }}
        >
          {/* Mark on dark */}
          <div
            style={{
              width: 56,
              height: 56,
              color: '#e2e8f0',
            }}
          >
            {concept.mark}
          </div>

          {/* Horizontal lockup on dark */}
          <div
            style={{
              marginTop: 16,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            <div style={{ width: 28, height: 28, color: '#e2e8f0', flexShrink: 0 }}>
              {concept.mark}
            </div>
            <span
              style={{
                fontSize: 'var(--text-xl)',
                fontWeight: 700,
                letterSpacing: '-0.025em',
                color: '#e2e8f0',
                fontFamily: 'var(--font-body)',
              }}
            >
              <span style={{ color: '#60a5fa' }}>AI</span>
              {' '}JobMatch
            </span>
          </div>

          {/* Favicon on dark */}
          <div
            style={{
              marginTop: 12,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                color: '#e2e8f0',
                background: '#1e293b',
                borderRadius: 6,
                border: '1px solid #334155',
                padding: 3,
                flexShrink: 0,
              }}
            >
              {concept.faviconMark}
            </div>
            <span
              style={{
                fontSize: '10px',
                color: '#64748b',
                textTransform: 'uppercase' as const,
                letterSpacing: '0.06em',
                fontWeight: 600,
              }}
            >
              32px favicon
            </span>
          </div>

          <p
            style={{
              fontSize: '10px',
              color: '#475569',
              marginTop: 6,
              textTransform: 'uppercase' as const,
              letterSpacing: '0.06em',
              fontWeight: 600,
            }}
          >
            тёмный фон
          </p>
        </div>
      </div>

      {/* Description */}
      <div
        style={{
          padding: '10px 16px 12px',
          borderTop: '1px solid var(--color-border)',
          background: 'white',
        }}
      >
        <p
          style={{
            fontSize: 'var(--text-sm)',
            color: 'var(--color-ink-secondary)',
            lineHeight: 'var(--leading-snug)',
            margin: 0,
          }}
        >
          {concept.description}
        </p>
      </div>
    </div>
  );
}

export default function LogoConcepts() {
  return (
    <section
      style={{
        marginTop: 32,
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border)',
        background: 'white',
        overflow: 'hidden',
      }}
    >
      {/* Section header */}
      <div
        style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--color-border)',
          background: 'linear-gradient(135deg, #f0f7ff 0%, #f8fafc 100%)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' as const }}>
          <h2
            style={{
              fontSize: 'var(--text-2xl)',
              fontWeight: 700,
              letterSpacing: '-0.02em',
              color: 'var(--color-ink)',
              margin: 0,
            }}
          >
            10 концепций логотипа — выберите одну
          </h2>
          <span
            style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase' as const,
              color: 'var(--color-accent)',
              border: '1px solid',
              borderColor: 'var(--color-accent)',
              borderRadius: 'var(--radius-full)',
              padding: '2px 10px',
              opacity: 0.75,
            }}
          >
            новое
          </span>
        </div>
        <p
          style={{
            marginTop: 6,
            fontSize: 'var(--text-sm)',
            color: 'var(--color-ink-secondary)',
          }}
        >
          Каждый вариант — знак, горизонтальная компоновка и 32px favicon. Светлый и тёмный фон рядом.
          Все SVG, без растра. Максимум 2 цвета: ink + accent.
        </p>
      </div>

      {/* Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
          gap: 1,
          background: 'var(--color-border)',
          padding: 1,
        }}
      >
        {concepts.map((c) => (
          <LogoCard key={c.id} concept={c} />
        ))}
      </div>
    </section>
  );
}
