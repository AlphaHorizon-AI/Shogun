import React from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';
import { useTranslation } from '../../i18n';

interface ShellProps {
  children: React.ReactNode;
}

export const Shell = ({ children }: ShellProps) => {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col h-screen w-screen bg-shogun-bg overflow-hidden text-shogun-text font-sans">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-8 relative scroll-smooth bg-shogun-card/30 flex flex-col">
          <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700 flex-1">
            {children}
          </div>
          <footer className="mt-12 py-6 border-t border-shogun-border/30 text-center">
            <p className="text-[10px] text-shogun-subdued uppercase tracking-widest font-bold">
              {t('common.copyright', '© 2026 Alpha Horizon. All rights reserved')}
            </p>
          </footer>
        </main>
      </div>
    </div>
  );
};
