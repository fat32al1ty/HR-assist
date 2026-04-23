import type { Metadata, Viewport } from 'next';
import './globals.css';
import { SessionProvider } from '@/lib/session';
import Topbar from '@/components/Topbar';

export const metadata: Metadata = {
  title: 'HR Помощник',
  description: 'Умный кабинет для анализа резюме и подбора вакансий',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru" data-theme="vercel">
      <body>
        <SessionProvider>
          <Topbar />
          {children}
          <div
            role="note"
            aria-label="Disclaimer"
            className="w-full border-t border-[var(--color-border)] bg-[var(--color-surface-muted,#f3f6fb)]/80 backdrop-blur-sm"
          >
            <p className="max-w-[1180px] mx-auto px-6 py-3 text-[length:var(--text-xs)] leading-[var(--leading-relaxed)] text-[color:var(--color-ink-muted)] text-center">
              Сервис не хранит персональные данные из резюме. Текст автоматически обезличивается
              перед обработкой, имена, телефоны и ссылки на профили удаляются, загруженный файл
              стирается сразу после анализа. Материалы предоставлены исключительно в ознакомительных
              и демонстрационных целях.
            </p>
          </div>
        </SessionProvider>
      </body>
    </html>
  );
}
