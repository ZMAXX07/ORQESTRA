import React, { useState } from 'react';
import { Header } from '../components/navigation/Header';
import { NavigationShell } from '../components/navigation/NavigationShell';
import './MainLayout.css';

export interface MainLayoutProps {
  children: React.ReactNode;
  isBackendHealthy: boolean | null;
  environmentName?: string;
  activeNavId?: string;
  onNavSelect?: (id: string) => void;
  onOpenSignIn?: () => void;
  onOpenStatus?: () => void;
}

export const MainLayout: React.FC<MainLayoutProps> = ({
  children,
  isBackendHealthy,
  environmentName,
  activeNavId,
  onNavSelect,
  onOpenSignIn,
  onOpenStatus,
}) => {
  const [isMobileNavOpen, setIsMobileNavOpen] = useState<boolean>(false);

  return (
    <div className="orq-layout-root">
      <Header
        isBackendHealthy={isBackendHealthy}
        environmentName={environmentName}
        onOpenSignIn={onOpenSignIn}
        onOpenStatus={onOpenStatus ?? (() => onNavSelect?.('system-status'))}
        isMobileMenuOpen={isMobileNavOpen}
        onToggleMobileMenu={() => setIsMobileNavOpen((prev) => !prev)}
      />
      <div className="orq-layout-body">
        <NavigationShell
          activeId={activeNavId}
          onSelect={onNavSelect}
          isMobileOpen={isMobileNavOpen}
          onCloseMobile={() => setIsMobileNavOpen(false)}
          environmentName={environmentName}
        />
        <main className="orq-layout-main" role="main">
          <div className="orq-main-container">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};

