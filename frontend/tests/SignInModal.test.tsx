import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { SignInModal } from '../src/components/auth/SignInModal';
import { AuthProvider } from '../src/context/AuthContext';

const renderWithAuth = async (ui: React.ReactElement) => {
  let rendered: ReturnType<typeof render>;
  await act(async () => {
    rendered = render(<AuthProvider>{ui}</AuthProvider>);
  });
  return rendered!;
};

describe('SignInModal Component', () => {
  it('renders form inputs and handles empty validation', async () => {
    const handleClose = vi.fn();
    await renderWithAuth(<SignInModal isOpen={true} onClose={handleClose} />);

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

  it('renders close button with accessible label and invokes onClose when clicked', async () => {
    const handleClose = vi.fn();
    await renderWithAuth(
      <SignInModal isOpen={true} onClose={handleClose} initialMode="signin" />
    );

    const closeBtn = screen.getByRole('button', { name: /Close dialog/i });
    expect(closeBtn).toBeInTheDocument();
    expect(closeBtn.className).toContain('orq-modal-close');

    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('renders close button in Create Account mode and invokes onClose', async () => {
    const handleClose = vi.fn();
    await renderWithAuth(
      <SignInModal isOpen={true} onClose={handleClose} initialMode="signup" />
    );

    expect(screen.getByText('Create Your Account')).toBeInTheDocument();
    const closeBtn = screen.getByRole('button', { name: /Close dialog/i });
    expect(closeBtn).toBeInTheDocument();

    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('closes modal on Escape key press', async () => {
    const handleClose = vi.fn();
    await renderWithAuth(<SignInModal isOpen={true} onClose={handleClose} />);

    fireEvent.keyDown(window, { key: 'Escape' });
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('does not render when isOpen is false', async () => {
    await renderWithAuth(<SignInModal isOpen={false} onClose={vi.fn()} />);

    expect(screen.queryByText('Operator Authentication')).not.toBeInTheDocument();
  });
});
