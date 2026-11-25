import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import { NavLink } from '@/components/ui';
import { Icon } from '@/components/icons/Icon';

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-jetbrains-mono',
});

export const metadata: Metadata = {
  title: 'DevOps Control Tower',
  description: 'Centralized command center for AI-powered development operations',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable}`}>
      <body>
        <div className="app-layout">
          <aside className="sidebar">
            <div className="sidebar-wordmark">
              <span className="brand-tile">DCT</span>
              <span className="brand-name">Control Tower</span>
            </div>

            <nav className="stack-2" style={{ gap: 4 }}>
              <NavLink href="/" icon="layout-dashboard">Overview</NavLink>
              <NavLink href="/reviews" icon="eye">Review queue</NavLink>
              <NavLink href="/design" icon="radar">Design system</NavLink>
            </nav>

            <div className="sidebar-spacer" />

            <div className="sidebar-user">
              <span className="sidebar-user__avatar">
                <Icon name="user" size={14} />
              </span>
              <div>
                <div className="sidebar-user__name">Operator</div>
                <div className="sidebar-user__role">Human review gate</div>
              </div>
            </div>
          </aside>

          <main className="main-content">
            <div className="page">{children}</div>
          </main>
        </div>
      </body>
    </html>
  );
}
