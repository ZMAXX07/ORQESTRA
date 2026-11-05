import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { SignInModal } from '../src/components/auth/SignInModal';
import { CreateBusinessModal } from '../src/components/onboarding/CreateBusinessModal';
import { AuthContext, AuthContextValue } from '../src/context/AuthContext';

// Base mock AuthContext factory
function createMockAuthContext(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  return {
    session: null,
    user: null,
    serverAuth: null,
    isLoading: false,
    isConfigured: true,
    authError: null,
    isRecoveryMode: false,
    setIsRecoveryMode: vi.fn(),
    signIn: vi.fn().mockResolvedValue({ success: true }),
    signUp: vi.fn().mockResolvedValue({ success: true, confirmationRequired: true }),
    resetPassword: vi.fn().mockResolvedValue({ success: true }),
    updatePassword: vi.fn().mockResolvedValue({ success: true }),
    signOut: vi.fn().mockResolvedValue(undefined),
    refreshServerAuth: vi.fn().mockResolvedValue(null),
    ...overrides,
  };
}

describe('Public User Registration & Business Onboarding Suite', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('1. Public Registration Form UI & Client-Side Validation', () => {
    it('renders Sign In and switches to Create Account view', () => {
      const mockAuth = createMockAuthContext();
      render(
        <AuthContext.Provider value={mockAuth}>
          <SignInModal isOpen={true} onClose={vi.fn()} />
        </AuthContext.Provider>
      );

      // Default is signin
      expect(screen.getByRole('tab', { name: 'Sign In' })).toHaveClass('active');
      expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();

      // Switch to signup via tab
      const createAccountTab = screen.getByRole('tab', { name: 'Create Account' });
      fireEvent.click(createAccountTab);

      expect(createAccountTab).toHaveClass('active');
      expect(screen.getByLabelText(/Full Name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Business Email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^Password/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Confirm Password/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Create Account' })).toBeInTheDocument();
    });

    it('validates required fields, email format, and password criteria on submit', async () => {
      const mockSignUp = vi.fn();
      const mockAuth = createMockAuthContext({ signUp: mockSignUp });

      render(
        <AuthContext.Provider value={mockAuth}>
          <SignInModal isOpen={true} onClose={vi.fn()} initialMode="signup" />
        </AuthContext.Provider>
      );

      const submitButton = screen.getByRole('button', { name: 'Create Account' });
      fireEvent.click(submitButton);

      // Validation errors should appear
      expect(await screen.findByText('Full name is required.')).toBeInTheDocument();
      expect(screen.getByText('Business email is required.')).toBeInTheDocument();
      expect(screen.getByText('Password is required.')).toBeInTheDocument();
      expect(screen.getByText('Please confirm your password.')).toBeInTheDocument();
      expect(mockSignUp).not.toHaveBeenCalled();

      // Test invalid email and weak password
      fireEvent.change(screen.getByLabelText(/Full Name/i), { target: { value: 'Alex Smith' } });
      fireEvent.change(screen.getByLabelText(/Business Email/i), { target: { value: 'not-an-email' } });
      fireEvent.change(screen.getByLabelText(/^Password/i), { target: { value: 'short' } });
      fireEvent.change(screen.getByLabelText(/Confirm Password/i), { target: { value: 'mismatch' } });

      fireEvent.click(submitButton);

      expect(await screen.findByText('Please enter a valid email address.')).toBeInTheDocument();
      expect(screen.getByText('Password must meet all complexity requirements.')).toBeInTheDocument();
      expect(screen.getByText('Passwords do not match.')).toBeInTheDocument();
      expect(mockSignUp).not.toHaveBeenCalled();
    });

    it('displays live password criteria feedback for length, letters, and numbers', () => {
      const mockAuth = createMockAuthContext();
      render(
        <AuthContext.Provider value={mockAuth}>
          <SignInModal isOpen={true} onClose={vi.fn()} initialMode="signup" />
        </AuthContext.Provider>
      );

      const passwordInput = screen.getByLabelText(/^Password/i);
      const minLengthCriteria = screen.getByText(/8 or more characters/i);
      const letterNumberCriteria = screen.getByText(/At least 1 letter and 1 number/i);

      expect(minLengthCriteria).not.toHaveClass('met');
      expect(letterNumberCriteria).not.toHaveClass('met');

      // Add only letters
      fireEvent.change(passwordInput, { target: { value: 'abcdefgh' } });
      expect(minLengthCriteria).toHaveClass('met');
      expect(letterNumberCriteria).not.toHaveClass('met');

      // Add numbers to meet both
      fireEvent.change(passwordInput, { target: { value: 'Secret123' } });
      expect(minLengthCriteria).toHaveClass('met');
      expect(letterNumberCriteria).toHaveClass('met');
    });

    it('toggles password visibility with show/hide button', () => {
      const mockAuth = createMockAuthContext();
      render(
        <AuthContext.Provider value={mockAuth}>
          <SignInModal isOpen={true} onClose={vi.fn()} initialMode="signup" />
        </AuthContext.Provider>
      );

      const passwordInput = screen.getByLabelText(/^Password/i);
      expect(passwordInput).toHaveAttribute('type', 'password');

      // Find toggle buttons by title
      const toggleButtons = screen.getAllByTitle('Show password');
      expect(toggleButtons.length).toBeGreaterThanOrEqual(1);

      // Click the first toggle
      fireEvent.click(toggleButtons[0]);
      expect(passwordInput).toHaveAttribute('type', 'text');

      // Click again to hide
      const hideButton = screen.getByTitle('Hide password');
      fireEvent.click(hideButton);
      expect(passwordInput).toHaveAttribute('type', 'password');
    });
  });

  describe('2. Registration Submission & Verification Pending State', () => {
    it('handles email verification pending state when mailer_autoconfirm is false', async () => {
      const mockSignUp = vi.fn().mockResolvedValue({
        success: true,
        confirmationRequired: true,
      });
      const mockAuth = createMockAuthContext({ signUp: mockSignUp });

      render(
        <AuthContext.Provider value={mockAuth}>
          <SignInModal isOpen={true} onClose={vi.fn()} initialMode="signup" />
        </AuthContext.Provider>
      );

      fireEvent.change(screen.getByLabelText(/Full Name/i), { target: { value: 'Jordan Lee' } });
      fireEvent.change(screen.getByLabelText(/Business Email/i), { target: { value: 'jordan@enterprise.com' } });
      fireEvent.change(screen.getByLabelText(/^Password/i), { target: { value: 'StrongPass123' } });
      fireEvent.change(screen.getByLabelText(/Confirm Password/i), { target: { value: 'StrongPass123' } });

      fireEvent.click(screen.getByRole('button', { name: 'Create Account' }));

      await waitFor(() => {
        expect(mockSignUp).toHaveBeenCalledWith('jordan@enterprise.com', 'StrongPass123', 'Jordan Lee');
      });

      // Verify pending notification
      expect(await screen.findByText('Verification Email Sent')).toBeInTheDocument();
      expect(screen.getByText(/We sent a confirmation link to/i)).toBeInTheDocument();
      expect(screen.getByText('jordan@enterprise.com')).toBeInTheDocument();

      // Proceed to sign in switches back to signin mode
      const proceedBtn = screen.getByRole('button', { name: 'Proceed to Sign In' });
      fireEvent.click(proceedBtn);
      expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
    });

    it('handles duplicate email error message cleanly', async () => {
      const mockSignUp = vi.fn().mockResolvedValue({
        success: false,
        error: 'An account with this email already exists. Please sign in or use password recovery.',
      });
      const mockAuth = createMockAuthContext({ signUp: mockSignUp });

      render(
        <AuthContext.Provider value={mockAuth}>
          <SignInModal isOpen={true} onClose={vi.fn()} initialMode="signup" />
        </AuthContext.Provider>
      );

      fireEvent.change(screen.getByLabelText(/Full Name/i), { target: { value: 'Alex Dupont' } });
      fireEvent.change(screen.getByLabelText(/Business Email/i), { target: { value: 'alex@existing.com' } });
      fireEvent.change(screen.getByLabelText(/^Password/i), { target: { value: 'Secret999' } });
      fireEvent.change(screen.getByLabelText(/Confirm Password/i), { target: { value: 'Secret999' } });

      fireEvent.click(screen.getByRole('button', { name: 'Create Account' }));

      expect(
        await screen.findByText(/An account with this email already exists/i)
      ).toBeInTheDocument();
    });
  });

  describe('3. Password Reset and Recovery Flow', () => {
    it('dispatches password reset email instructions and shows success message', async () => {
      const mockResetPassword = vi.fn().mockResolvedValue({ success: true });
      const mockAuth = createMockAuthContext({ resetPassword: mockResetPassword });

      render(
        <AuthContext.Provider value={mockAuth}>
          <SignInModal isOpen={true} onClose={vi.fn()} />
        </AuthContext.Provider>
      );

      // Click "Forgot password?"
      fireEvent.click(screen.getByText('Forgot password?'));

      expect(screen.getByText('Reset Password')).toBeInTheDocument();
      const emailInput = screen.getByLabelText(/Business Email/i);
      fireEvent.change(emailInput, { target: { value: 'operator@orqestra.io' } });

      fireEvent.click(screen.getByRole('button', { name: 'Send Recovery Email' }));

      await waitFor(() => {
        expect(mockResetPassword).toHaveBeenCalledWith('operator@orqestra.io');
      });

      expect(await screen.findByText('Recovery Email Dispatched')).toBeInTheDocument();
    });

    it('handles password recovery mode to set new password', async () => {
      const mockUpdatePassword = vi.fn().mockResolvedValue({ success: true });
      const mockSetIsRecoveryMode = vi.fn();
      const mockAuth = createMockAuthContext({
        isRecoveryMode: true,
        updatePassword: mockUpdatePassword,
        setIsRecoveryMode: mockSetIsRecoveryMode,
      });

      render(
        <AuthContext.Provider value={mockAuth}>
          <SignInModal isOpen={true} onClose={vi.fn()} initialMode="recovery" />
        </AuthContext.Provider>
      );

      expect(screen.getByText('Set New Password')).toBeInTheDocument();

      const newPassInput = screen.getByLabelText(/^New Password/i);
      const confirmPassInput = screen.getByLabelText(/Confirm New Password/i);

      fireEvent.change(newPassInput, { target: { value: 'NewSuperSecret123' } });
      fireEvent.change(confirmPassInput, { target: { value: 'NewSuperSecret123' } });

      fireEvent.click(screen.getByRole('button', { name: 'Update Password' }));

      await waitFor(() => {
        expect(mockUpdatePassword).toHaveBeenCalledWith('NewSuperSecret123');
      });

      expect(await screen.findByText('Password Updated')).toBeInTheDocument();
      expect(mockSetIsRecoveryMode).toHaveBeenCalledWith(false);
    });
  });

  describe('4. Business Workspace Onboarding for New Registered User', () => {
    it('prompts user with no business to create their initial business workspace', () => {
      // Mock an authenticated user with no active business membership
      const mockAuth = createMockAuthContext({
        user: { id: 'usr-new-001', email: 'newuser@domain.com' } as any,
        session: { access_token: 'valid-jwt-token' } as any,
        serverAuth: {
          status: 'authenticated',
          user: { user_id: 'usr-new-001', email: 'newuser@domain.com' },
          active_business: undefined,
          memberships: [],
        },
      });

      render(
        <AuthContext.Provider value={mockAuth}>
          <CreateBusinessModal isOpen={true} onSuccess={vi.fn()} />
        </AuthContext.Provider>
      );

      expect(screen.getByText('Create Your Business')).toBeInTheDocument();
      expect(screen.getByLabelText(/Operating Name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Country \/ Region/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Primary Operating Currency/i)).toBeInTheDocument();

      // Cancel button should be hidden for initial workspace creation (only Sign Out is visible)
      expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /Create Business/i })).toBeInTheDocument();
    });

    it('auto-syncs primary operating currency when country is selected', () => {
      const mockAuth = createMockAuthContext();
      render(
        <AuthContext.Provider value={mockAuth}>
          <CreateBusinessModal isOpen={true} onSuccess={vi.fn()} />
        </AuthContext.Provider>
      );

      const countrySelect = screen.getByLabelText(/Country \/ Region/i);
      const currencySelect = screen.getByLabelText(/Primary Operating Currency/i) as HTMLSelectElement;

      // Default is India -> INR
      expect(currencySelect.value).toBe('INR');

      // Select United States -> USD
      fireEvent.change(countrySelect, { target: { value: 'US' } });
      expect(currencySelect.value).toBe('USD');

      // Select United Kingdom -> GBP
      fireEvent.change(countrySelect, { target: { value: 'GB' } });
      expect(currencySelect.value).toBe('GBP');

      // Select European Union -> EUR
      fireEvent.change(countrySelect, { target: { value: 'EU' } });
      expect(currencySelect.value).toBe('EUR');

      // Select Canada -> CAD
      fireEvent.change(countrySelect, { target: { value: 'CA' } });
      expect(currencySelect.value).toBe('CAD');

      // Select Japan -> JPY
      fireEvent.change(countrySelect, { target: { value: 'JP' } });
      expect(currencySelect.value).toBe('JPY');
    });

    it('allows existing users with memberships to skip onboarding and see workspace', () => {
      const mockAuth = createMockAuthContext({
        user: { id: 'usr-existing-001', email: 'owner@acme.com' } as any,
        session: { access_token: 'valid-jwt-token' } as any,
        serverAuth: {
          status: 'authenticated',
          user: { user_id: 'usr-existing-001', email: 'owner@acme.com' },
          active_business: {
            business_id: 'biz-001',
            business_name: 'Acme Global',
            role: 'owner',
            currency: 'USD',
            is_active: true,
          },
          memberships: [
            {
              business_id: 'biz-001',
              business_name: 'Acme Global',
              role: 'owner',
              is_active: true,
            },
          ],
        },
      });

      render(
        <AuthContext.Provider value={mockAuth}>
          <CreateBusinessModal isOpen={false} onSuccess={vi.fn()} />
        </AuthContext.Provider>
      );

      expect(screen.queryByText('Register Business Workspace')).not.toBeInTheDocument();
    });
  });

  describe('5. Sign In, Sign Out & Session Security', () => {
    it('executes sign-in with valid credentials and closes modal', async () => {
      const mockSignIn = vi.fn().mockResolvedValue({ success: true });
      const handleClose = vi.fn();
      const mockAuth = createMockAuthContext({ signIn: mockSignIn });

      render(
        <AuthContext.Provider value={mockAuth}>
          <SignInModal isOpen={true} onClose={handleClose} />
        </AuthContext.Provider>
      );

      fireEvent.change(screen.getByLabelText(/Business Email/i), {
        target: { value: 'demo@gmail.com' },
      });
      fireEvent.change(screen.getByLabelText(/^Password/i), {
        target: { value: 'SecretPassword123' },
      });

      fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));

      await waitFor(() => {
        expect(mockSignIn).toHaveBeenCalledWith('demo@gmail.com', 'SecretPassword123');
        expect(handleClose).toHaveBeenCalled();
      });
    });

    it('displays error on invalid credentials', async () => {
      const mockSignIn = vi.fn().mockResolvedValue({
        success: false,
        error: 'Invalid login credentials. Please check your email and password.',
      });
      const mockAuth = createMockAuthContext({ signIn: mockSignIn });

      render(
        <AuthContext.Provider value={mockAuth}>
          <SignInModal isOpen={true} onClose={vi.fn()} />
        </AuthContext.Provider>
      );

      fireEvent.change(screen.getByLabelText(/Business Email/i), {
        target: { value: 'wrong@domain.com' },
      });
      fireEvent.change(screen.getByLabelText(/^Password/i), {
        target: { value: 'wrongpass' },
      });

      fireEvent.click(screen.getByRole('button', { name: 'Sign In' }));

      expect(
        await screen.findByText('Invalid login credentials. Please check your email and password.')
      ).toBeInTheDocument();
    });
  });
});
