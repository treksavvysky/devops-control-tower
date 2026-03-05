import type { Metadata } from 'next';
import './globals.css';
import Link from 'next/link';

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
    <html lang="en">
      <body>
        <div className="app-layout">
          <aside className="sidebar">
            <div style={{ marginBottom: '2rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--accent-blue)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 'bold' }}>
                DCT
              </div>
              <h2 style={{ fontSize: '1.2rem', fontWeight: 600 }}>Orchestrator</h2>
            </div>
            
            <nav style={{ display: 'flex', flexDirection: 'column' }}>
              <Link href="/" className="nav-link">Overview</Link>
              <Link href="/reviews" className="nav-link">Human Reviews</Link>
            </nav>
            
            <div style={{ marginTop: 'auto', padding: '1rem', background: 'rgba(255,255,255,0.03)', borderRadius: 8, fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              <strong>Jules Core</strong> - v1.0.0
            </div>
          </aside>
          
          <main className="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
