import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Card, CardHeader, CardTitle, CardBody } from '../common/Card';
import { Button } from '../common/Button';
import { Alert } from '../common/Alert';
import {
  createAndVerifyBusiness,
  generateSlug,
  validateBusinessName,
  validateBusinessSlug,
  OnboardingResult,
  OnboardingError,
} from '../../services/onboarding';
import { CurrencySelect } from '../common/CurrencySelect';
import { detectUserDefaultCurrency } from '../../utils/currencies';
import './CreateBusinessModal.css';

export interface CreateBusinessModalProps {
  isOpen: boolean;
  onSuccess?: (result: OnboardingResult) => void;
  onSignOut?: () => void;
}

export const CreateBusinessModal: React.FC<CreateBusinessModalProps> = ({
  isOpen,
  onSuccess,
  onSignOut,
}) => {
  const { user, refreshServerAuth, signOut } = useAuth();

  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [currency, setCurrency] = useState(() => detectUserDefaultCurrency());
  const [country, setCountry] = useState(() =>
    detectUserDefaultCurrency() === 'INR' ? 'IN' : 'US'
  );
  const [isManualSlug, setIsManualSlug] = useState(false);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [stepStatus, setStepStatus] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [nameError, setNameError] = useState<string | null>(null);
  const [slugError, setSlugError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleCountryChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newCountry = e.target.value;
    setCountry(newCountry);
    const countryCurrencyMap: Record<string, string> = {
      IN: 'INR',
      US: 'USD',
      GB: 'GBP',
      EU: 'EUR',
      CA: 'CAD',
      AU: 'AUD',
      AE: 'AED',
      SG: 'SGD',
      JP: 'JPY',
    };
    if (countryCurrencyMap[newCountry]) {
      setCurrency(countryCurrencyMap[newCountry]);
    }
  };

  const handleNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setName(val);
    setNameError(null);
    setErrorMsg(null);

    if (!isManualSlug) {
      setSlug(generateSlug(val));
      setSlugError(null);
    }
  };

  const handleSlugChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setIsManualSlug(true);
    const val = e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '');
    setSlug(val);
    setSlugError(null);
    setErrorMsg(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    // Validate inputs
    const nameVal = validateBusinessName(name);
    if (!nameVal.isValid) {
      setNameError(nameVal.error || 'Business name is required.');
      return;
    }

    if (slug.trim()) {
      const slugVal = validateBusinessSlug(slug);
      if (!slugVal.isValid) {
        setSlugError(slugVal.error || 'Invalid slug format.');
        return;
      }
    }

    if (!user?.id) {
      setErrorMsg('Authenticated user session not found. Please sign in again.');
      return;
    }

    setIsSubmitting(true);
    setStepStatus('Registering business workspace...');

    try {
      setStepStatus('Creating business and verifying owner membership...');
      const result = await createAndVerifyBusiness(
        {
          name: name.trim(),
          slug: slug.trim() || undefined,
          currency,
        },
        user.id
      );

      setStepStatus('Updating server authorization context...');
      await refreshServerAuth();

      onSuccess?.(result);
    } catch (err: unknown) {
      if (err instanceof OnboardingError) {
        if (err.code === 'DUPLICATE_SLUG') {
          setSlugError(err.message);
        }
        setErrorMsg(err.message);
      } else {
        const msg = err instanceof Error ? err.message : 'An unexpected error occurred.';
        setErrorMsg(msg);
      }
    } finally {
      setIsSubmitting(false);
      setStepStatus(null);
    }
  };

  const handleSignOutClick = async () => {
    if (onSignOut) {
      onSignOut();
    } else {
      await signOut();
    }
  };

  return (
    <div
      className="orq-onboarding-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-biz-title"
      data-testid="create-business-modal"
    >
      <div className="orq-onboarding-container">
        <Card className="orq-onboarding-card">
          <CardHeader className="orq-onboarding-header">
            <div className="orq-onboarding-brand">
              <img
                src="/orqestra-icon.png"
                alt="Orqestra"
                className="orq-onboarding-logo"
                width="34"
                height="34"
              />
              <div>
                <CardTitle id="create-biz-title">Create Your Business</CardTitle>
                <p className="orq-onboarding-subtitle">
                  Set up your business workspace to begin orchestrating operations.
                </p>
              </div>
            </div>
          </CardHeader>

          <CardBody>
            {errorMsg && (
              <Alert type="error" title="Setup Notice" className="orq-onboarding-alert">
                <span>{errorMsg}</span>
              </Alert>
            )}

            <form onSubmit={handleSubmit} className="orq-onboarding-form" noValidate>
              <div className="orq-form-group">
                <label htmlFor="biz-name-input" className="orq-form-label">
                  Business Legal / Operating Name <span className="orq-required-mark">*</span>
                </label>
                <input
                  id="biz-name-input"
                  type="text"
                  className={`orq-form-input ${nameError ? 'is-invalid' : ''}`}
                  value={name}
                  onChange={handleNameChange}
                  placeholder="e.g., Northwind Traders"
                  disabled={isSubmitting}
                  autoFocus
                  required
                  data-testid="biz-name-input"
                />
                {nameError && (
                  <span className="orq-field-error" role="alert">
                    {nameError}
                  </span>
                )}
              </div>

              <div className="orq-form-group">
                <label htmlFor="biz-slug-input" className="orq-form-label">
                  Workspace Slug
                </label>
                <div className="orq-slug-input-wrap">
                  <span className="orq-slug-prefix" aria-hidden="true">
                    orqestra.app/
                  </span>
                  <input
                    id="biz-slug-input"
                    type="text"
                    className={`orq-form-input orq-slug-field ${slugError ? 'is-invalid' : ''}`}
                    value={slug}
                    onChange={handleSlugChange}
                    placeholder="northwind-traders"
                    disabled={isSubmitting}
                    data-testid="biz-slug-input"
                  />
                </div>
                {slugError ? (
                  <span className="orq-field-error" role="alert">
                    {slugError}
                  </span>
                ) : (
                  <span className="orq-form-hint">
                    Unique workspace URL identifier. Auto-generated from name or custom.
                  </span>
                )}
              </div>

              <div className="orq-form-row">
                <div className="orq-form-group">
                  <label htmlFor="biz-country-select" className="orq-form-label">
                    Operating Country / Region
                  </label>
                  <select
                    id="biz-country-select"
                    className="orq-form-select"
                    value={country}
                    onChange={handleCountryChange}
                    disabled={isSubmitting}
                  >
                    <option value="IN">India</option>
                    <option value="US">United States</option>
                    <option value="GB">United Kingdom</option>
                    <option value="EU">European Union (Eurozone)</option>
                    <option value="CA">Canada</option>
                    <option value="AU">Australia</option>
                    <option value="AE">United Arab Emirates</option>
                    <option value="SG">Singapore</option>
                    <option value="JP">Japan</option>
                    <option value="OTHER">Other Region</option>
                  </select>
                </div>

                <div className="orq-form-group">
                  <label htmlFor="biz-currency-select" className="orq-form-label">
                    Primary Operating Currency
                  </label>
                  <CurrencySelect
                    id="biz-currency-select"
                    value={currency}
                    onChange={(newCurr) => setCurrency(newCurr)}
                    disabled={isSubmitting}
                  />
                </div>
              </div>
              <span className="orq-form-hint" style={{ marginTop: '-8px', marginBottom: '12px' }}>
                Authoritative base currency for product catalog, orders, and sequential invoices.
              </span>

              {stepStatus && (
                <div className="orq-onboarding-progress" role="status" aria-live="polite">
                  <div className="orq-onboarding-spinner" aria-hidden="true" />
                  <span>{stepStatus}</span>
                </div>
              )}

              <div className="orq-onboarding-actions">
                <Button
                  type="button"
                  variant="outline"
                  onClick={handleSignOutClick}
                  disabled={isSubmitting}
                  className="orq-onboarding-signout-btn"
                >
                  Sign Out
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  isLoading={isSubmitting}
                  disabled={isSubmitting || !name.trim()}
                  data-testid="create-biz-submit-btn"
                >
                  <span>Create Business</span>
                  <span aria-hidden="true">→</span>
                </Button>
              </div>
            </form>
          </CardBody>
        </Card>
      </div>
    </div>
  );
};
