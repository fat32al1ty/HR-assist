import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'HR Помощник',
  description: 'Умный кабинет для анализа резюме и подбора вакансий'
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
