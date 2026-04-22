import type { Metadata } from 'next';
import './globals.css';
import { SessionProvider } from '@/lib/session';
import Topbar from '@/components/Topbar';

export const metadata: Metadata = {
  title: 'HR Помощник',
  description: 'Умный кабинет для анализа резюме и подбора вакансий',
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
        </SessionProvider>
      </body>
    </html>
  );
}
