import React, { useState, useMemo } from 'react';
import {
  ISO_CURRENCIES,
  CurrencyInfo,
  getCurrencyInfo,
  formatCurrency,
} from '../../utils/currencies';
import './CurrencySelect.css';

export interface CurrencySelectProps {
  id?: string;
  value: string;
  onChange: (currencyCode: string) => void;
  disabled?: boolean;
  className?: string;
}

const POPULAR_SHORTCUTS = ['INR', 'USD', 'EUR', 'GBP', 'AED', 'SAR', 'JPY', 'CAD', 'AUD'];

export const CurrencySelect: React.FC<CurrencySelectProps> = ({
  id = 'biz-currency-select',
  value,
  onChange,
  disabled = false,
  className = '',
}) => {
  const [searchQuery, setSearchQuery] = useState('');

  const selectedInfo = useMemo(() => getCurrencyInfo(value), [value]);

  const filteredCurrencies = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return ISO_CURRENCIES;

    const matches = ISO_CURRENCIES.filter(
      (c) =>
        c.code.toLowerCase().includes(q) ||
        c.name.toLowerCase().includes(q) ||
        c.symbol.toLowerCase().includes(q)
    );

    // Ensure currently selected currency is always available in the option list
    if (selectedInfo && !matches.some((c) => c.code === selectedInfo.code)) {
      return [selectedInfo, ...matches];
    }

    return matches;
  }, [searchQuery, selectedInfo]);

  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onChange(e.target.value);
  };

  const handleShortcutClick = (code: string) => {
    if (disabled) return;
    onChange(code);
  };

  const previewAmount = value === 'JPY' || value === 'KRW' ? 150000 : 15000;
  const sampleFormatted = formatCurrency(previewAmount, value);

  return (
    <div className={`orq-currency-select-container ${className}`}>
      {/* Quick Select Popular Badges for 1-click selection */}
      <div className="orq-currency-shortcuts" aria-label="Popular Currencies">
        <span className="orq-currency-shortcuts-label">Quick select:</span>
        {POPULAR_SHORTCUTS.map((code) => {
          const info = getCurrencyInfo(code);
          const isSelected = value === code;
          return (
            <button
              key={code}
              type="button"
              className={`orq-currency-chip ${isSelected ? 'is-active' : ''}`}
              onClick={() => handleShortcutClick(code)}
              disabled={disabled}
              title={`${info.name} (${info.symbol})`}
              data-testid={`currency-chip-${code}`}
            >
              {code} {info.symbol}
            </button>
          );
        })}
      </div>

      {/* Main Accessible Selector with clear high-contrast options */}
      <select
        id={id}
        className="orq-form-select orq-currency-dropdown"
        value={value}
        onChange={handleSelectChange}
        disabled={disabled}
        data-testid={id}
        aria-label="Primary Operating Currency"
      >
        {filteredCurrencies.map((c: CurrencyInfo) => (
          <option key={c.code} value={c.code}>
            {c.label}
          </option>
        ))}
      </select>

      {/* Search Filter Bar with icon & clear button */}
      <div className="orq-currency-search-wrap">
        <span className="orq-currency-search-icon" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        </span>
        <input
          type="search"
          className="orq-form-input orq-currency-search-input"
          placeholder="Search by code, name, or symbol (e.g. INR, Rupee, ₹, USD, Euro)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          disabled={disabled}
          aria-label="Search currency by code, name, or symbol"
          data-testid="currency-search-input"
        />
        <div className="orq-currency-search-meta">
          {searchQuery && (
            <>
              <span className="orq-currency-count-badge">
                {filteredCurrencies.length} found
              </span>
              <button
                type="button"
                className="orq-currency-clear-btn"
                onClick={() => setSearchQuery('')}
                title="Clear currency search"
                aria-label="Clear currency search"
              >
                ×
              </button>
            </>
          )}
        </div>
      </div>

      {/* Live Locale Preview */}
      <div className="orq-currency-preview" data-testid="currency-preview">
        <span className="orq-currency-preview-code">
          {selectedInfo.code} ({selectedInfo.symbol})
        </span>
        <span className="orq-currency-preview-sample">
          Sample Format: <strong>{sampleFormatted}</strong>
        </span>
      </div>
    </div>
  );
};
