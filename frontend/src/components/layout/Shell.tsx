import React from 'react';
import { Sidebar } from './Sidebar';
import { TopBar } from './TopBar';

interface ShellProps {
  children: React.ReactNode;
}

export const Shell = ({ children }: ShellProps) => {
  return (
    <div className="flex flex-col h-screen w-screen bg-shogun-bg overflow-hidden text-shogun-text font-sans">
      <TopBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-8 relative scroll-smooth bg-shogun-card/30">
          <div className="max-w-7xl mx-auto space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
