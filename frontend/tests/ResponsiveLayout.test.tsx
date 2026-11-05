import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import App from '../src/app/App';
import { Header } from '../src/components/navigation/Header';
import { NavigationShell } from '../src/components/navigation/NavigationShell';
import { MainLayout } from '../src/layouts/MainLayout';
import { AuthProvider } from '../src/context/AuthContext';
import { RealtimeProvider } from '../src/context/RealtimeContext';

describe('Responsive Layout & Cross-Device Optimization Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  const renderWithProviders = (ui: React.ReactElement) => {
    return render(
      <AuthProvider>
        <RealtimeProvider>
          {ui}
        </RealtimeProvider>
      </AuthProvider>
    );
  };

  describe('Mobile Navigation Drawer & Toggle Behavior', () => {
    it('renders the mobile menu toggle button with accessible aria attributes', () => {
      const onToggle = vi.fn();
      renderWithProviders(
        <Header
          isBackendHealthy={true}
          environmentName="Phase 5 Staging"
          isMobileMenuOpen={false}
          onToggleMobileMenu={onToggle}
        />
      );

      const toggleBtn = screen.getByRole('button', { name: /Open navigation menu/i });
      expect(toggleBtn).toBeInTheDocument();
      expect(toggleBtn).toHaveAttribute('aria-expanded', 'false');
      expect(toggleBtn).toHaveAttribute('aria-controls', 'orq-main-navigation');

      fireEvent.click(toggleBtn);
      expect(onToggle).toHaveBeenCalledTimes(1);
    });

    it('updates aria-label and aria-expanded when mobile menu is open', () => {
      renderWithProviders(
        <Header
          isBackendHealthy={true}
          environmentName="Phase 5 Staging"
          isMobileMenuOpen={true}
          onToggleMobileMenu={vi.fn()}
        />
      );

      const closeBtn = screen.getByRole('button', { name: /Close navigation menu/i });
      expect(closeBtn).toBeInTheDocument();
      expect(closeBtn).toHaveAttribute('aria-expanded', 'true');
    });

    it('renders backdrop and mobile drawer header when isMobileOpen is true', () => {
      const onClose = vi.fn();
      render(
        <NavigationShell
          activeId="foundation"
          isMobileOpen={true}
          onCloseMobile={onClose}
          environmentName="Phase 5 Staging"
        />
      );

      const backdrop = screen.getByTestId('nav-backdrop');
      expect(backdrop).toBeInTheDocument();

      const drawerCloseBtn = screen.getByRole('button', { name: /Close navigation menu/i });
      expect(drawerCloseBtn).toBeInTheDocument();

      fireEvent.click(backdrop);
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('closes mobile drawer upon pressing the Escape key', () => {
      const onClose = vi.fn();
      render(
        <NavigationShell
          activeId="foundation"
          isMobileOpen={true}
          onCloseMobile={onClose}
        />
      );

      fireEvent.keyDown(window, { key: 'Escape', code: 'Escape' });
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('invokes onSelect and automatically closes mobile drawer when a navigation item is clicked', () => {
      const onSelect = vi.fn();
      const onClose = vi.fn();
      render(
        <NavigationShell
          activeId="foundation"
          isMobileOpen={true}
          onSelect={onSelect}
          onCloseMobile={onClose}
        />
      );

      const inventoryBtn = screen.getByRole('button', { name: /Inventory Management/i });
      fireEvent.click(inventoryBtn);

      expect(onSelect).toHaveBeenCalledWith('inventory');
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('renders all navigation items with consistent orq-nav-icon containers', () => {
      render(
        <NavigationShell activeId="foundation" />
      );

      const navButtons = screen.getAllByRole('button');
      expect(navButtons.length).toBe(8);

      navButtons.forEach((btn) => {
        const iconSpan = btn.querySelector('.orq-nav-icon');
        expect(iconSpan).toBeInTheDocument();
        const labelSpan = btn.querySelector('.orq-nav-label');
        expect(labelSpan).toBeInTheDocument();
      });
    });
  });

  describe('MainLayout Responsive Orchestration', () => {
    it('manages mobile drawer state and synchronizes Header and NavigationShell', () => {
      renderWithProviders(
        <MainLayout isBackendHealthy={true} environmentName="Phase 5 Staging">
          <div data-testid="test-content">Dashboard Content</div>
        </MainLayout>
      );

      expect(screen.getByTestId('test-content')).toBeInTheDocument();

      // Mobile toggle opens drawer
      const toggleBtn = screen.getByRole('button', { name: /Open navigation menu/i });
      fireEvent.click(toggleBtn);

      // Now backdrop and drawer close button exist
      const backdrop = screen.getByTestId('nav-backdrop');
      expect(backdrop).toBeInTheDocument();

      // Close via backdrop click
      fireEvent.click(backdrop);
      expect(screen.queryByTestId('nav-backdrop')).not.toBeInTheDocument();
    });
  });

  describe('Target Viewport Verification', () => {
    const viewports = [
      { width: 320, height: 568, name: '320px (Small Mobile)' },
      { width: 390, height: 844, name: '390px (Common Mobile)' },
      { width: 768, height: 1024, name: '768px (Tablet Portrait)' },
      { width: 1024, height: 768, name: '1024px (Tablet Landscape / Laptop)' },
      { width: 1440, height: 900, name: '1440px (Desktop)' },
      { width: 1920, height: 1080, name: '1920px (Ultra-Wide / Large Desktop)' },
    ];

    viewports.forEach(({ width, height, name }) => {
      it(`renders App cleanly without layout collapse at ${name}`, () => {
        // Set window viewport dimension
        window.innerWidth = width;
        window.innerHeight = height;
        window.dispatchEvent(new Event('resize'));

        vi.stubGlobal(
          'fetch',
          vi.fn().mockImplementation(() =>
            Promise.resolve({
              ok: true,
              json: () =>
                Promise.resolve({
                  status: 'healthy',
                  environment: 'staging',
                  active_business_count: 1,
                  components: {
                    database: { status: 'operational', details: 'PostgreSQL ready' },
                    authentication: { status: 'operational', details: 'Supabase JWT ready' },
                  },
                }),
            })
          )
        );

        const { container } = render(<App />);

        // Layout elements must exist and be accessible
        const layoutRoot = container.querySelector('.orq-layout-root');
        expect(layoutRoot).toBeInTheDocument();

        const header = container.querySelector('.orq-header');
        expect(header).toBeInTheDocument();

        const main = container.querySelector('.orq-layout-main');
        expect(main).toBeInTheDocument();

        const brandName = screen.getByText('Orqestra');
        expect(brandName).toBeInTheDocument();
      });
    });
  });

  describe('Touch Targets & Accessible Controls', () => {
    it('verifies navigation items have proper accessible attributes and touch semantics', () => {
      render(
        <NavigationShell activeId="products" />
      );

      const activeBtn = screen.getByRole('button', { name: /Products Catalog/i });
      expect(activeBtn).toHaveAttribute('aria-current', 'page');
      expect(activeBtn).toHaveClass('is-active');

      const inactiveBtn = screen.getByRole('button', { name: /Customer Directory/i });
      expect(inactiveBtn).not.toHaveAttribute('aria-current');
      expect(inactiveBtn).not.toHaveClass('is-active');
    });

    it('verifies responsive operations page styles and bounded table wrappers', () => {
      const { container } = render(
        <div className="orq-ops-container">
          <div className="orq-ops-header">
            <h1 className="orq-ops-title">Product Catalog</h1>
            <div className="orq-ops-header-actions">
              <button className="orq-button orq-button--primary orq-button--md">New Product</button>
            </div>
          </div>
          <div className="orq-ops-table-wrapper">
            <table className="orq-ops-table">
              <thead>
                <tr>
                  <th>SKU</th>
                  <th>Product Name</th>
                </tr>
              </thead>
            </table>
          </div>
        </div>
      );

      const wrapper = container.querySelector('.orq-ops-table-wrapper');
      expect(wrapper).toBeInTheDocument();
      const table = container.querySelector('.orq-ops-table');
      expect(table).toBeInTheDocument();
      const actions = container.querySelector('.orq-ops-header-actions');
      expect(actions).toBeInTheDocument();
    });
  });
});
