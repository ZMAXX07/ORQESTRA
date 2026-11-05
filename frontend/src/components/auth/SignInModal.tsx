import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../common/Button';
import { Alert } from '../common/Alert';
import { Card, CardHeader, CardTitle, CardBody } from '../common/Card';
import { XIcon } from '../icons/Icons';
import './SignInModal.css';

export type AuthModalMode = 'signin' | 'signup' | 'forgot' | 'recovery';

export interface SignInModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialMode?: AuthModalMode;
}

export const SignInModal: React.FC<SignInModalProps> = ({
  isOpen,
  onClose,
  initialMode = 'signin',
}) => {
  const {
    signIn,
    signUp,
    resetPassword,
    updatePassword,
    isConfigured,
    authError,
    isRecoveryMode,
    setIsRecoveryMode,
  } = useAuth();

  const [mode, setMode] = useState<AuthModalMode>(() =>
    isRecoveryMode ? 'recovery' : initialMode
  );

  // Form states
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  // Status & error states
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{
    fullName?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});

  // Success states
  const [confirmationPending, setConfirmationPending] = useState(false);
  const [resetSent, setResetSent] = useState(false);
  const [recoverySuccess, setRecoverySuccess] = useState(false);

  // Sync mode if initialMode or isRecoveryMode changes when opening
  useEffect(() => {
    if (isOpen) {
      setMode(isRecoveryMode ? 'recovery' : initialMode);
      setLocalError(null);
      setFieldErrors({});
      setConfirmationPending(false);
      setResetSent(false);
      setRecoverySuccess(false);
    }
  }, [isOpen, initialMode, isRecoveryMode]);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const validateEmail = (val: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val.trim());
  };

  const hasMinLength = password.length >= 8;
  const hasLetter = /[a-zA-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const isPasswordValid = hasMinLength && hasLetter && hasNumber;

  const switchMode = (newMode: AuthModalMode) => {
    setMode(newMode);
    setLocalError(null);
    setFieldErrors({});
    setConfirmationPending(false);
    setResetSent(false);
    setRecoverySuccess(false);
  };

  const handleSignInSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    setFieldErrors({});

    const trimmedEmail = email.trim();
    if (!trimmedEmail || !password.trim()) {
      setLocalError('Please enter both email and password.');
      return;
    }

    if (!validateEmail(trimmedEmail)) {
      setFieldErrors({ email: 'Please enter a valid email address.' });
      return;
    }

    setIsSubmitting(true);
    const result = await signIn(trimmedEmail, password);
    setIsSubmitting(false);

    if (result.success) {
      onClose();
    } else if (result.error) {
      setLocalError(result.error);
    }
  };

  const handleSignUpSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    const errors: typeof fieldErrors = {};

    const trimmedName = fullName.trim();
    const trimmedEmail = email.trim();

    if (!trimmedName) {
      errors.fullName = 'Full name is required.';
    } else if (trimmedName.length < 2) {
      errors.fullName = 'Full name must be at least 2 characters.';
    }

    if (!trimmedEmail) {
      errors.email = 'Business email is required.';
    } else if (!validateEmail(trimmedEmail)) {
      errors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      errors.password = 'Password is required.';
    } else if (!isPasswordValid) {
      errors.password = 'Password must meet all complexity requirements.';
    }

    if (!confirmPassword) {
      errors.confirmPassword = 'Please confirm your password.';
    } else if (password !== confirmPassword) {
      errors.confirmPassword = 'Passwords do not match.';
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    if (!signUp) {
      setLocalError('Public sign up is not configured or supported.');
      return;
    }

    setIsSubmitting(true);
    const result = await signUp(trimmedEmail, password, trimmedName);
    setIsSubmitting(false);

    if (result.success) {
      if (result.confirmationRequired) {
        setConfirmationPending(true);
      } else {
        onClose();
      }
    } else if (result.error) {
      setLocalError(result.error);
    }
  };

  const handleForgotSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    setFieldErrors({});

    const trimmedEmail = email.trim();
    if (!trimmedEmail) {
      setFieldErrors({ email: 'Please enter your business email address.' });
      return;
    }
    if (!validateEmail(trimmedEmail)) {
      setFieldErrors({ email: 'Please enter a valid email address.' });
      return;
    }

    if (!resetPassword) {
      setLocalError('Password recovery is not configured or supported.');
      return;
    }

    setIsSubmitting(true);
    const result = await resetPassword(trimmedEmail);
    setIsSubmitting(false);

    if (result.success) {
      setResetSent(true);
    } else if (result.error) {
      setLocalError(result.error);
    }
  };

  const handleRecoverySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    const errors: typeof fieldErrors = {};

    if (!password) {
      errors.password = 'New password is required.';
    } else if (!isPasswordValid) {
      errors.password = 'Password must be at least 8 characters with a letter and a number.';
    }

    if (!confirmPassword) {
      errors.confirmPassword = 'Please confirm your new password.';
    } else if (password !== confirmPassword) {
      errors.confirmPassword = 'Passwords do not match.';
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    if (!updatePassword) {
      setLocalError('Password update is not configured or supported.');
      return;
    }

    setIsSubmitting(true);
    const result = await updatePassword(password);
    setIsSubmitting(false);

    if (result.success) {
      setRecoverySuccess(true);
      setIsRecoveryMode?.(false);
    } else if (result.error) {
      setLocalError(result.error);
    }
  };

  const displayedError = localError || authError;

  return (
    <div
      className="orq-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="signin-title"
      data-testid="auth-modal"
    >
      <div className="orq-modal-container">
        <Card className="orq-signin-card">
          <CardHeader className="orq-signin-header">
            <div className="orq-signin-title-wrap">
              <img
                src="/orqestra-icon.png"
                alt="Orqestra"
                className="orq-signin-logo"
                width="32"
                height="32"
              />
              <div className="orq-signin-title-text">
                <CardTitle id="signin-title" className="orq-signin-title">
                  {mode === 'signup'
                    ? 'Create Your Account'
                    : mode === 'forgot'
                    ? 'Reset Password'
                    : mode === 'recovery'
                    ? 'Set New Password'
                    : 'Operator Authentication'}
                </CardTitle>
                <p className="orq-auth-subtitle">
                  {mode === 'signup'
                    ? 'Register to create and orchestrate your business workspace'
                    : mode === 'forgot'
                    ? 'Enter your email to receive recovery instructions'
                    : mode === 'recovery'
                    ? 'Enter your new account password'
                    : 'Sign in to access your operations dashboard'}
                </p>
              </div>
            </div>
            <button
              type="button"
              className="orq-modal-close"
              onClick={onClose}
              aria-label="Close dialog"
            >
              <XIcon size={20} />
            </button>
          </CardHeader>
          <CardBody>
            {/* Mode Switcher for standard sign-in / registration */}
            {(mode === 'signin' || mode === 'signup') && (
              <div className="orq-auth-tabs" role="tablist" aria-label="Authentication Options">
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === 'signin'}
                  className={`orq-auth-tab ${mode === 'signin' ? 'active' : ''}`}
                  onClick={() => switchMode('signin')}
                  disabled={isSubmitting}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === 'signup'}
                  className={`orq-auth-tab ${mode === 'signup' ? 'active' : ''}`}
                  onClick={() => switchMode('signup')}
                  disabled={isSubmitting}
                >
                  Create Account
                </button>
              </div>
            )}

            {!isConfigured && (
              <Alert type="warning" title="Supabase Not Configured">
                Supabase credentials (VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY) are not set
                in frontend .env. Configure them to authenticate against your Supabase project.
              </Alert>
            )}

            {displayedError && !confirmationPending && !resetSent && !recoverySuccess && (
              <Alert type="error" title="Authentication Error">
                {displayedError}
              </Alert>
            )}

            {/* Email Confirmation Pending State */}
            {confirmationPending && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                <Alert type="info" title="Verification Email Sent">
                  We sent a confirmation link to <strong>{email}</strong>. Please check your inbox
                  and click the link to verify your email, then return here to sign in and set up
                  your business workspace.
                </Alert>
                <Button variant="primary" size="md" onClick={() => switchMode('signin')}>
                  Proceed to Sign In
                </Button>
              </div>
            )}

            {/* Password Reset Sent State */}
            {resetSent && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                <Alert type="success" title="Recovery Email Dispatched">
                  Password reset instructions have been sent to <strong>{email}</strong> if an account
                  exists with that address.
                </Alert>
                <Button variant="outline" size="md" onClick={() => switchMode('signin')}>
                  Back to Sign In
                </Button>
              </div>
            )}

            {/* Password Recovery Succeeded State */}
            {recoverySuccess && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                <Alert type="success" title="Password Updated">
                  Your password has been changed successfully. You may now sign in with your new password.
                </Alert>
                <Button variant="primary" size="md" onClick={() => switchMode('signin')}>
                  Sign In
                </Button>
              </div>
            )}

            {/* SIGN IN FORM */}
            {mode === 'signin' && !confirmationPending && (
              <form onSubmit={handleSignInSubmit} className="orq-signin-form" noValidate>
                <div className="orq-form-group">
                  <label htmlFor="signin-email" className="orq-form-label">
                    Business Email
                  </label>
                  <input
                    id="signin-email"
                    type="email"
                    className={`orq-form-input ${fieldErrors.email ? 'is-invalid' : ''}`}
                    placeholder="operator@company.com"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      if (fieldErrors.email) setFieldErrors({ ...fieldErrors, email: undefined });
                    }}
                    disabled={!isConfigured || isSubmitting}
                    autoComplete="email"
                    required
                  />
                  {fieldErrors.email && (
                    <span className="orq-field-error" role="alert">
                      {fieldErrors.email}
                    </span>
                  )}
                </div>

                <div className="orq-form-group">
                  <div className="orq-form-row-split">
                    <label htmlFor="signin-password" className="orq-form-label">
                      Password
                    </label>
                    <button
                      type="button"
                      className="orq-link-button"
                      onClick={() => switchMode('forgot')}
                      disabled={isSubmitting}
                      style={{ fontSize: '11px' }}
                    >
                      Forgot password?
                    </button>
                  </div>
                  <div className="orq-password-wrap">
                    <input
                      id="signin-password"
                      type={showPassword ? 'text' : 'password'}
                      className="orq-form-input"
                      placeholder="••••••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      disabled={!isConfigured || isSubmitting}
                      autoComplete="current-password"
                      required
                    />
                    <button
                      type="button"
                      className="orq-password-toggle"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Hide credentials' : 'Show credentials'}
                      title={showPassword ? 'Hide password' : 'Show password'}
                      tabIndex={0}
                    >
                      {showPassword ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                <div className="orq-signin-actions">
                  <Button
                    type="button"
                    variant="outline"
                    size="md"
                    onClick={onClose}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    isLoading={isSubmitting}
                    disabled={!isConfigured || isSubmitting}
                  >
                    Sign In
                  </Button>
                </div>

                <div className="orq-auth-switch">
                  <span>Don't have an account?</span>
                  <button
                    type="button"
                    className="orq-link-button"
                    onClick={() => switchMode('signup')}
                    disabled={isSubmitting}
                  >
                    Create Account
                  </button>
                </div>
              </form>
            )}

            {/* CREATE ACCOUNT / SIGN UP FORM */}
            {mode === 'signup' && !confirmationPending && (
              <form onSubmit={handleSignUpSubmit} className="orq-signin-form" noValidate>
                <div className="orq-form-group">
                  <label htmlFor="signup-name" className="orq-form-label">
                    Full Name <span style={{ color: 'var(--color-error)' }}>*</span>
                  </label>
                  <input
                    id="signup-name"
                    type="text"
                    className={`orq-form-input ${fieldErrors.fullName ? 'is-invalid' : ''}`}
                    placeholder="e.g. Sarah Jenkins"
                    value={fullName}
                    onChange={(e) => {
                      setFullName(e.target.value);
                      if (fieldErrors.fullName) setFieldErrors({ ...fieldErrors, fullName: undefined });
                    }}
                    disabled={!isConfigured || isSubmitting}
                    autoComplete="name"
                    required
                  />
                  {fieldErrors.fullName && (
                    <span className="orq-field-error" role="alert">
                      {fieldErrors.fullName}
                    </span>
                  )}
                </div>

                <div className="orq-form-group">
                  <label htmlFor="signup-email" className="orq-form-label">
                    Business Email <span style={{ color: 'var(--color-error)' }}>*</span>
                  </label>
                  <input
                    id="signup-email"
                    type="email"
                    className={`orq-form-input ${fieldErrors.email ? 'is-invalid' : ''}`}
                    placeholder="sarah@company.com"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      if (fieldErrors.email) setFieldErrors({ ...fieldErrors, email: undefined });
                    }}
                    disabled={!isConfigured || isSubmitting}
                    autoComplete="email"
                    required
                  />
                  {fieldErrors.email && (
                    <span className="orq-field-error" role="alert">
                      {fieldErrors.email}
                    </span>
                  )}
                </div>

                <div className="orq-form-group">
                  <label htmlFor="signup-password" className="orq-form-label">
                    Password <span style={{ color: 'var(--color-error)' }}>*</span>
                  </label>
                  <div className="orq-password-wrap">
                    <input
                      id="signup-password"
                      type={showPassword ? 'text' : 'password'}
                      className={`orq-form-input ${fieldErrors.password ? 'is-invalid' : ''}`}
                      placeholder="At least 8 characters"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (fieldErrors.password) setFieldErrors({ ...fieldErrors, password: undefined });
                      }}
                      disabled={!isConfigured || isSubmitting}
                      autoComplete="new-password"
                      required
                    />
                    <button
                      type="button"
                      className="orq-password-toggle"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Hide credentials' : 'Show credentials'}
                      title={showPassword ? 'Hide password' : 'Show password'}
                      tabIndex={0}
                    >
                      {showPassword ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                      )}
                    </button>
                  </div>
                  {fieldErrors.password && (
                    <span className="orq-field-error" role="alert">
                      {fieldErrors.password}
                    </span>
                  )}
                  {/* Live Password Requirements checklist */}
                  <div className="orq-password-criteria" data-testid="password-criteria">
                    <span className={`orq-criterion ${hasMinLength ? 'met' : ''}`}>
                      {hasMinLength ? '✓' : '•'} 8 or more characters
                    </span>
                    <span className={`orq-criterion ${hasLetter && hasNumber ? 'met' : ''}`}>
                      {hasLetter && hasNumber ? '✓' : '•'} At least 1 letter and 1 number
                    </span>
                  </div>
                </div>

                <div className="orq-form-group">
                  <label htmlFor="signup-confirm-password" className="orq-form-label">
                    Confirm Password <span style={{ color: 'var(--color-error)' }}>*</span>
                  </label>
                  <div className="orq-password-wrap">
                    <input
                      id="signup-confirm-password"
                      type={showConfirmPassword ? 'text' : 'password'}
                      className={`orq-form-input ${fieldErrors.confirmPassword ? 'is-invalid' : ''}`}
                      placeholder="Re-enter password"
                      value={confirmPassword}
                      onChange={(e) => {
                        setConfirmPassword(e.target.value);
                        if (fieldErrors.confirmPassword) setFieldErrors({ ...fieldErrors, confirmPassword: undefined });
                      }}
                      disabled={!isConfigured || isSubmitting}
                      autoComplete="new-password"
                      required
                    />
                    <button
                      type="button"
                      className="orq-password-toggle"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      aria-label={showConfirmPassword ? 'Hide credentials' : 'Show credentials'}
                      title={showConfirmPassword ? 'Hide password' : 'Show password'}
                      tabIndex={0}
                    >
                      {showConfirmPassword ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                      )}
                    </button>
                  </div>
                  {fieldErrors.confirmPassword && (
                    <span className="orq-field-error" role="alert">
                      {fieldErrors.confirmPassword}
                    </span>
                  )}
                </div>

                <div className="orq-signin-actions">
                  <Button
                    type="button"
                    variant="outline"
                    size="md"
                    onClick={onClose}
                    disabled={isSubmitting}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    isLoading={isSubmitting}
                    disabled={!isConfigured || isSubmitting}
                  >
                    Create Account
                  </Button>
                </div>

                <div className="orq-auth-switch">
                  <span>Already have an account?</span>
                  <button
                    type="button"
                    className="orq-link-button"
                    onClick={() => switchMode('signin')}
                    disabled={isSubmitting}
                  >
                    Sign In
                  </button>
                </div>
              </form>
            )}

            {/* FORGOT PASSWORD FORM */}
            {mode === 'forgot' && !resetSent && (
              <form onSubmit={handleForgotSubmit} className="orq-signin-form" noValidate>
                <div className="orq-form-group">
                  <label htmlFor="forgot-email" className="orq-form-label">
                    Business Email
                  </label>
                  <input
                    id="forgot-email"
                    type="email"
                    className={`orq-form-input ${fieldErrors.email ? 'is-invalid' : ''}`}
                    placeholder="operator@company.com"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      if (fieldErrors.email) setFieldErrors({ ...fieldErrors, email: undefined });
                    }}
                    disabled={!isConfigured || isSubmitting}
                    autoComplete="email"
                    required
                  />
                  {fieldErrors.email && (
                    <span className="orq-field-error" role="alert">
                      {fieldErrors.email}
                    </span>
                  )}
                </div>

                <div className="orq-signin-actions">
                  <Button
                    type="button"
                    variant="outline"
                    size="md"
                    onClick={() => switchMode('signin')}
                    disabled={isSubmitting}
                  >
                    Back
                  </Button>
                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    isLoading={isSubmitting}
                    disabled={!isConfigured || isSubmitting}
                  >
                    Send Recovery Email
                  </Button>
                </div>
              </form>
            )}

            {/* RECOVERY / SET NEW PASSWORD FORM */}
            {mode === 'recovery' && !recoverySuccess && (
              <form onSubmit={handleRecoverySubmit} className="orq-signin-form" noValidate>
                <div className="orq-form-group">
                  <label htmlFor="recovery-password" className="orq-form-label">
                    New Password
                  </label>
                  <div className="orq-password-wrap">
                    <input
                      id="recovery-password"
                      type={showPassword ? 'text' : 'password'}
                      className={`orq-form-input ${fieldErrors.password ? 'is-invalid' : ''}`}
                      placeholder="At least 8 characters"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (fieldErrors.password) setFieldErrors({ ...fieldErrors, password: undefined });
                      }}
                      disabled={!isConfigured || isSubmitting}
                      autoComplete="new-password"
                      required
                    />
                    <button
                      type="button"
                      className="orq-password-toggle"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Hide credentials' : 'Show credentials'}
                      title={showPassword ? 'Hide password' : 'Show password'}
                      tabIndex={0}
                    >
                      {showPassword ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                      )}
                    </button>
                  </div>
                  {fieldErrors.password && (
                    <span className="orq-field-error" role="alert">
                      {fieldErrors.password}
                    </span>
                  )}
                  <div className="orq-password-criteria" data-testid="password-criteria">
                    <span className={`orq-criterion ${hasMinLength ? 'met' : ''}`}>
                      {hasMinLength ? '✓' : '•'} 8 or more characters
                    </span>
                    <span className={`orq-criterion ${hasLetter && hasNumber ? 'met' : ''}`}>
                      {hasLetter && hasNumber ? '✓' : '•'} At least 1 letter and 1 number
                    </span>
                  </div>
                </div>

                <div className="orq-form-group">
                  <label htmlFor="recovery-confirm-password" className="orq-form-label">
                    Confirm New Password
                  </label>
                  <div className="orq-password-wrap">
                    <input
                      id="recovery-confirm-password"
                      type={showConfirmPassword ? 'text' : 'password'}
                      className={`orq-form-input ${fieldErrors.confirmPassword ? 'is-invalid' : ''}`}
                      placeholder="Re-enter new password"
                      value={confirmPassword}
                      onChange={(e) => {
                        setConfirmPassword(e.target.value);
                        if (fieldErrors.confirmPassword) setFieldErrors({ ...fieldErrors, confirmPassword: undefined });
                      }}
                      disabled={!isConfigured || isSubmitting}
                      autoComplete="new-password"
                      required
                    />
                    <button
                      type="button"
                      className="orq-password-toggle"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      aria-label={showConfirmPassword ? 'Hide credentials' : 'Show credentials'}
                      title={showConfirmPassword ? 'Hide password' : 'Show password'}
                      tabIndex={0}
                    >
                      {showConfirmPassword ? (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      ) : (
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                      )}
                    </button>
                  </div>
                  {fieldErrors.confirmPassword && (
                    <span className="orq-field-error" role="alert">
                      {fieldErrors.confirmPassword}
                    </span>
                  )}
                </div>

                <div className="orq-signin-actions">
                  <Button
                    type="submit"
                    variant="primary"
                    size="md"
                    isLoading={isSubmitting}
                    disabled={!isConfigured || isSubmitting}
                  >
                    Update Password
                  </Button>
                </div>
              </form>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
};
