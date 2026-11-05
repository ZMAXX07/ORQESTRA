import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SignInModal } from '../src/components/auth/SignInModal';
import { AuthProvider } from '../src/context/AuthContext';

describe('SignInModal Component', () => {
  it('renders form inputs and handles empty validation', () => {
    const handleClose = vi.fn();
    render(
      <AuthProvider>
        <SignInModal isOpen={true} onClose={handleClose} />
      </AuthProvider>
    );

    expect(screen.getByText('Operator Authentication')).toBeInTheDocument();
    expect(screen.getByLabelText(/Business Email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Password/i)).toBeInTheDocument();

    const submitButton = screen.getByRole('button', { name: 'Sign In' });
    fireEvent.click(submitButton);

    // Should indicate Supabase configuration requirement or field validation
    expect(
      screen.getByText(/Supabase Not Configured|Please enter both email and password/i)
    ).toBeInTheDocument();
  });

  it('renders close button with accessible label and invokes onClose when clicked', () => {
    const handleClose = vi.fn();
    render(
      <AuthProvider>
        <SignInModal isOpen={true} onClose={handleClose} initialMode="signin" />
      </AuthProvider>
    );

    const closeBtn = screen.getByRole('button', { name: /Close dialog/i });
    expect(closeBtn).toBeInTheDocument();
    expect(closeBtn.className).toContain('orq-modal-close');

    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('renders close button in Create Account mode and invokes onClose', () => {
    const handleClose = vi.fn();
    render(
      <AuthProvider>
        <SignInModal isOpen={true} onClose={handleClose} initialMode="signup" />
      </AuthProvider>
    );

    expect(screen.getByText('Create Your Account')).toBeInTheDocument();
    const closeBtn = screen.getByRole('button', { name: /Close dialog/i });
    expect(closeBtn).toBeInTheDocument();

    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('closes modal on Escape key press', () => {
    const handleClose = vi.fn();
    render(
      <AuthProvider>
        <SignInModal isOpen={true} onClose={handleClose} />
      </AuthProvider>
    );

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('does not render when isOpen is false', () => {
    render(
      <AuthProvider>
        <SignInModal isOpen={false} onClose={vi.fn()} />
      </AuthProvider>
    );

    expect(screen.queryByText('Operator Authentication')).not.toBeInTheDocument();
  });
});
