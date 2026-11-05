import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import {
  ISO_CURRENCIES,
  isValidCurrencyCode,
  getCurrencyInfo,
  getCurrencySymbol,
  detectUserDefaultCurrency,
  formatCurrency,
} from '../src/utils/currencies';
import { CurrencySelect } from '../src/components/common/CurrencySelect';
import { CreateBusinessModal } from '../src/components/onboarding/CreateBusinessModal';
import { AuthContext, AuthContextValue } from '../src/context/AuthContext';
import { Session, User } from '@supabase/supabase-js';
import * as onboardingService from '../src/services/onboarding';

describe('World Currencies & Business Onboarding Suite', () => {
  describe('1. ISO 4217 Currency Registry & Required Currencies', () => {
    const requiredCurrencies = [
      { code: 'INR', name: 'Indian Rupee', symbol: '₹', label: 'INR - Indian Rupee (₹)' },
      { code: 'USD', name: 'United States Dollar', symbol: '$', label: 'USD - United States Dollar ($)' },
      { code: 'EUR', name: 'Euro', symbol: '€', label: 'EUR - Euro (€)' },
      { code: 'GBP', name: 'Pound Sterling', symbol: '£', label: 'GBP - Pound Sterling (£)' },
      { code: 'CAD', name: 'Canadian Dollar', symbol: 'C$', label: 'CAD - Canadian Dollar (C$)' },
      { code: 'AUD', name: 'Australian Dollar', symbol: 'A$', label: 'AUD - Australian Dollar (A$)' },
      { code: 'JPY', name: 'Japanese Yen', symbol: '¥', label: 'JPY - Japanese Yen (¥)' },
      { code: 'CNY', name: 'Chinese Yuan', symbol: '¥', label: 'CNY - Chinese Yuan (¥)' },
      { code: 'SGD', name: 'Singapore Dollar', symbol: 'S$', label: 'SGD - Singapore Dollar (S$)' },
      { code: 'AED', name: 'UAE Dirham', symbol: 'د.إ', label: 'AED - UAE Dirham (د.إ)' },
      { code: 'SAR', name: 'Saudi Riyal', symbol: 'ر.س', label: 'SAR - Saudi Riyal (ر.س)' },
      { code: 'CHF', name: 'Swiss Franc', symbol: 'CHF', label: 'CHF - Swiss Franc (CHF)' },
      { code: 'NZD', name: 'New Zealand Dollar', symbol: 'NZ$', label: 'NZD - New Zealand Dollar (NZ$)' },
      { code: 'ZAR', name: 'South African Rand', symbol: 'R', label: 'ZAR - South African Rand (R)' },
      { code: 'BRL', name: 'Brazilian Real', symbol: 'R$', label: 'BRL - Brazilian Real (R$)' },
      { code: 'MXN', name: 'Mexican Peso', symbol: '$', label: 'MXN - Mexican Peso ($)' },
      { code: 'KRW', name: 'South Korean Won', symbol: '₩', label: 'KRW - South Korean Won (₩)' },
      { code: 'HKD', name: 'Hong Kong Dollar', symbol: 'HK$', label: 'HKD - Hong Kong Dollar (HK$)' },
      { code: 'SEK', name: 'Swedish Krona', symbol: 'kr', label: 'SEK - Swedish Krona (kr)' },
      { code: 'NOK', name: 'Norwegian Krone', symbol: 'kr', label: 'NOK - Norwegian Krone (kr)' },
      { code: 'DKK', name: 'Danish Krone', symbol: 'kr', label: 'DKK - Danish Krone (kr)' },
      { code: 'THB', name: 'Thai Baht', symbol: '฿', label: 'THB - Thai Baht (฿)' },
      { code: 'MYR', name: 'Malaysian Ringgit', symbol: 'RM', label: 'MYR - Malaysian Ringgit (RM)' },
      { code: 'IDR', name: 'Indonesian Rupiah', symbol: 'Rp', label: 'IDR - Indonesian Rupiah (Rp)' },
      { code: 'PHP', name: 'Philippine Peso', symbol: '₱', label: 'PHP - Philippine Peso (₱)' },
      { code: 'PKR', name: 'Pakistani Rupee', symbol: '₨', label: 'PKR - Pakistani Rupee (₨)' },
      { code: 'BDT', name: 'Bangladeshi Taka', symbol: '৳', label: 'BDT - Bangladeshi Taka (৳)' },
      { code: 'LKR', name: 'Sri Lankan Rupee', symbol: 'Rs', label: 'LKR - Sri Lankan Rupee (Rs)' },
      { code: 'NPR', name: 'Nepalese Rupee', symbol: 'Rs', label: 'NPR - Nepalese Rupee (Rs)' },
      { code: 'NGN', name: 'Nigerian Naira', symbol: '₦', label: 'NGN - Nigerian Naira (₦)' },
      { code: 'EGP', name: 'Egyptian Pound', symbol: 'E£', label: 'EGP - Egyptian Pound (E£)' },
      { code: 'KES', name: 'Kenyan Shilling', symbol: 'KSh', label: 'KES - Kenyan Shilling (KSh)' },
      { code: 'TRY', name: 'Turkish Lira', symbol: '₺', label: 'TRY - Turkish Lira (₺)' },
      { code: 'PLN', name: 'Polish Złoty', symbol: 'zł', label: 'PLN - Polish Złoty (zł)' },
      { code: 'CZK', name: 'Czech Koruna', symbol: 'Kč', label: 'CZK - Czech Koruna (Kč)' },
      { code: 'HUF', name: 'Hungarian Forint', symbol: 'Ft', label: 'HUF - Hungarian Forint (Ft)' },
      { code: 'ILS', name: 'Israeli New Shekel', symbol: '₪', label: 'ILS - Israeli New Shekel (₪)' },
      { code: 'QAR', name: 'Qatari Riyal', symbol: 'ر.ق', label: 'QAR - Qatari Riyal (ر.ق)' },
      { code: 'KWD', name: 'Kuwaiti Dinar', symbol: 'د.ك', label: 'KWD - Kuwaiti Dinar (د.ك)' },
      { code: 'BHD', name: 'Bahraini Dinar', symbol: 'د.ب', label: 'BHD - Bahraini Dinar (د.ب)' },
      { code: 'OMR', name: 'Omani Rial', symbol: 'ر.ع.', label: 'OMR - Omani Rial (ر.ع.)' },
    ];

    it('contains all 41 explicitly required world currencies with exact labels and symbols', () => {
      expect(requiredCurrencies.length).toBe(41);
      for (const item of requiredCurrencies) {
        expect(isValidCurrencyCode(item.code)).toBe(true);
        const info = getCurrencyInfo(item.code);
        expect(info.code).toBe(item.code);
        expect(info.name).toBe(item.name);
        expect(info.symbol).toBe(item.symbol);
        expect(info.label).toBe(item.label);
        expect(getCurrencySymbol(item.code)).toBe(item.symbol);
      }
    });

    it('contains a comprehensive maintained ISO 4217 dataset (>140 active world currencies)', () => {
      expect(ISO_CURRENCIES.length).toBeGreaterThan(140);
    });

    it('correctly maps decimal precision per ISO 4217 standard', () => {
      expect(getCurrencyInfo('JPY').decimals).toBe(0);
      expect(getCurrencyInfo('KRW').decimals).toBe(0);
      expect(getCurrencyInfo('VND').decimals).toBe(0);
      expect(getCurrencyInfo('KWD').decimals).toBe(3);
      expect(getCurrencyInfo('BHD').decimals).toBe(3);
      expect(getCurrencyInfo('OMR').decimals).toBe(3);
      expect(getCurrencyInfo('USD').decimals).toBe(2);
      expect(getCurrencyInfo('INR').decimals).toBe(2);
      expect(getCurrencyInfo('EUR').decimals).toBe(2);
    });

    it('rejects invalid or obsolete currency codes', () => {
      expect(isValidCurrencyCode('')).toBe(false);
      expect(isValidCurrencyCode('   ')).toBe(false);
      expect(isValidCurrencyCode('INVALID')).toBe(false);
      expect(isValidCurrencyCode('XYZ')).toBe(false);
      expect(isValidCurrencyCode('DEM')).toBe(false); // Obsolete German Mark
      expect(isValidCurrencyCode('FRF')).toBe(false); // Obsolete French Franc
      expect(isValidCurrencyCode('123')).toBe(false);
    });
  });

  describe('2. Locale-Aware Default Currency Detection', () => {
    const originalDateTimeFormat = Intl.DateTimeFormat;

    afterEach(() => {
      Intl.DateTimeFormat = originalDateTimeFormat;
      vi.restoreAllMocks();
    });

    it('defaults to INR when time zone is Asia/Kolkata', () => {
      const mockResolved = {
        resolvedOptions: () => ({ timeZone: 'Asia/Kolkata' } as Intl.ResolvedDateTimeFormatOptions),
      };
      Intl.DateTimeFormat = vi.fn().mockImplementation(() => mockResolved) as any;

      expect(detectUserDefaultCurrency()).toBe('INR');
    });

    it('defaults to INR when navigator language is en-IN or hi-IN', () => {
      const mockResolved = {
        resolvedOptions: () => ({ timeZone: 'UTC' } as Intl.ResolvedDateTimeFormatOptions),
      };
      Intl.DateTimeFormat = vi.fn().mockImplementation(() => mockResolved) as any;

      vi.spyOn(navigator, 'language', 'get').mockReturnValue('en-IN');
      expect(detectUserDefaultCurrency()).toBe('INR');
    });

    it('defaults to USD when locale is non-India (e.g. en-US / America/New_York)', () => {
      const mockResolved = {
        resolvedOptions: () => ({ timeZone: 'America/New_York' } as Intl.ResolvedDateTimeFormatOptions),
      };
      Intl.DateTimeFormat = vi.fn().mockImplementation(() => mockResolved) as any;

      vi.spyOn(navigator, 'language', 'get').mockReturnValue('en-US');
      expect(detectUserDefaultCurrency()).toBe('USD');
    });
  });

  describe('3. Financial Formatting Utility (formatCurrency)', () => {
    it('formats INR with rupee symbol and Indian lakhs/crores grouping', () => {
      const formatted = formatCurrency(150000, 'INR', { locale: 'en-IN' });
      expect(formatted).toMatch(/₹\s?1,50,000\.00/);
    });

    it('formats USD with dollar symbol and standard 2 decimals', () => {
      const formatted = formatCurrency(1500, 'USD', { locale: 'en-US' });
      expect(formatted).toBe('$1,500.00');
    });

    it('formats EUR with euro symbol and 2 decimals', () => {
      const formatted = formatCurrency(1500, 'EUR', { locale: 'en-US' });
      expect(formatted).toMatch(/€\s?1,500\.00/);
    });

    it('formats JPY with 0 decimal places per ISO 4217 standard', () => {
      const formatted = formatCurrency(1500, 'JPY', { locale: 'en-US' });
      expect(formatted).toBe('¥1,500');
    });

    it('supports useGrouping: false for compact unformatted values', () => {
      expect(formatCurrency(1250, 'USD', { useGrouping: false, locale: 'en-US' })).toBe('$1250.00');
      expect(formatCurrency(1250, 'INR', { useGrouping: false, locale: 'en-IN' })).toMatch(/₹\s?1250\.00/);
      expect(formatCurrency(1250, 'JPY', { useGrouping: false, locale: 'en-US' })).toBe('¥1250');
    });

    it('safely handles zero, null, and string inputs', () => {
      expect(formatCurrency(0, 'USD', { locale: 'en-US' })).toBe('$0.00');
      expect(formatCurrency('25.50', 'USD', { locale: 'en-US' })).toBe('$25.50');
      expect(formatCurrency(null, 'USD', { locale: 'en-US' })).toBe('$0.00');
    });
  });

  describe('4. Searchable Accessible CurrencySelect Component', () => {
    it('renders with initial currency and options formatted as CODE - Name (Symbol)', () => {
      const handleChange = vi.fn();
      render(<CurrencySelect value="USD" onChange={handleChange} />);

      const select = screen.getByRole('combobox', { name: /Primary Operating Currency/i });
      expect(select).toBeInTheDocument();
      expect(select).toHaveValue('USD');

      expect(screen.getByText('USD - United States Dollar ($)')).toBeInTheDocument();
      expect(screen.getByText('INR - Indian Rupee (₹)')).toBeInTheDocument();
      expect(screen.getByText('EUR - Euro (€)')).toBeInTheDocument();
    });

    it('filters currency options in real-time when search query is typed', () => {
      const handleChange = vi.fn();
      render(<CurrencySelect value="USD" onChange={handleChange} />);

      const searchInput = screen.getByTestId('currency-search-input');
      fireEvent.change(searchInput, { target: { value: 'rupee' } });

      // Indian Rupee, Pakistani Rupee, etc. should match
      expect(screen.getByText('INR - Indian Rupee (₹)')).toBeInTheDocument();
      expect(screen.getByText('PKR - Pakistani Rupee (₨)')).toBeInTheDocument();
      // Unrelated currencies should be filtered out
      expect(screen.queryByText('JPY - Japanese Yen (¥)')).not.toBeInTheDocument();
    });

    it('provides quick select chips for popular currencies including INR and AED', () => {
      const handleChange = vi.fn();
      render(<CurrencySelect value="USD" onChange={handleChange} />);

      const inrChip = screen.getByTestId('currency-chip-INR');
      expect(inrChip).toBeInTheDocument();
      fireEvent.click(inrChip);
      expect(handleChange).toHaveBeenCalledWith('INR');

      const aedChip = screen.getByTestId('currency-chip-AED');
      expect(aedChip).toBeInTheDocument();
      fireEvent.click(aedChip);
      expect(handleChange).toHaveBeenCalledWith('AED');
    });

    it('displays live locale sample preview matching selected currency', () => {
      const { rerender } = render(<CurrencySelect value="INR" onChange={vi.fn()} />);
      const preview = screen.getByTestId('currency-preview');
      expect(preview).toHaveTextContent('INR (₹)');
      expect(preview).toHaveTextContent('₹');

      rerender(<CurrencySelect value="JPY" onChange={vi.fn()} />);
      expect(preview).toHaveTextContent('JPY (¥)');
      expect(preview).toHaveTextContent('¥');
    });
  });

  describe('5. Onboarding Form Currency Integration & Boundary Enforcement', () => {
    const mockAuthContext: AuthContextValue = {
      user: { id: 'usr_operator_inr', email: 'operator@orqestra.in' } as User,
      session: { access_token: 'valid_jwt_mock' } as Session,
      serverAuth: {
        status: 'authenticated',
        user: { user_id: 'usr_operator_inr', email: 'operator@orqestra.in' },
        memberships: [],
      },
      isLoading: false,
      isConfigured: true,
      authError: null,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshServerAuth: vi.fn().mockResolvedValue(undefined),
    };

    it('rejects invalid currency codes during business creation service execution', async () => {
      await expect(
        onboardingService.createAndVerifyBusiness(
          { name: 'Test Org', currency: 'INVALID' },
          'usr_test'
        )
      ).rejects.toThrow(/unsupported or invalid iso 4217 currency code/i);
    });

    it('allows operator to select INR and persists ISO code upon onboarding submission', async () => {
      const createSpy = vi
        .spyOn(onboardingService, 'createAndVerifyBusiness')
        .mockResolvedValue({
          business: {
            id: 'biz_delhi_101',
            name: 'Bharat Logistics',
            slug: 'bharat-logistics',
            currency: 'INR',
            is_active: true,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
          membership: {
            id: 'mem_101',
            business_id: 'biz_delhi_101',
            user_id: 'usr_operator_inr',
            role: 'owner',
            is_active: true,
          },
        });

      const handleSuccess = vi.fn();

      render(
        <AuthContext.Provider value={mockAuthContext}>
          <CreateBusinessModal isOpen={true} onSuccess={handleSuccess} />
        </AuthContext.Provider>
      );

      // Enter business name
      fireEvent.change(screen.getByTestId('biz-name-input'), {
        target: { value: 'Bharat Logistics' },
      });

      // Select INR currency via quick chip or selector
      const inrChip = screen.getByTestId('currency-chip-INR');
      fireEvent.click(inrChip);

      // Submit form
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /Create Business/i }));
      });

      await waitFor(() => {
        expect(createSpy).toHaveBeenCalledWith(
          {
            name: 'Bharat Logistics',
            slug: 'bharat-logistics',
            currency: 'INR',
          },
          'usr_operator_inr'
        );
      });
    });

    it('preserves user selected currency when form re-renders from other field changes', () => {
      render(
        <AuthContext.Provider value={mockAuthContext}>
          <CreateBusinessModal isOpen={true} onSuccess={vi.fn()} />
        </AuthContext.Provider>
      );

      // Select EUR
      const eurChip = screen.getByTestId('currency-chip-EUR');
      fireEvent.click(eurChip);
      expect(screen.getByTestId('biz-currency-select')).toHaveValue('EUR');

      // Trigger re-renders by typing in name and slug
      fireEvent.change(screen.getByTestId('biz-name-input'), {
        target: { value: 'European Traders' },
      });
      fireEvent.change(screen.getByTestId('biz-slug-input'), {
        target: { value: 'euro-traders' },
      });

      // Currency must remain EUR
      expect(screen.getByTestId('biz-currency-select')).toHaveValue('EUR');
    });
  });
});
