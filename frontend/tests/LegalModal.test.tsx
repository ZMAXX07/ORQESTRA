import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { LegalModal } from '../src/components/legal/LegalModal';

describe('LegalModal Component (Legal & Launch Essentials)', () => {
  it('does not render when isOpen is false', () => {
    const { container } = render(
      <LegalModal isOpen={false} onClose={vi.fn()} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders Terms of Service by default when open', () => {
    render(<LegalModal isOpen={true} onClose={vi.fn()} initialDoc="terms" />);

    expect(screen.getByTestId('legal-modal')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Terms of Service' })).toBeInTheDocument();
    expect(
      screen.getByText(/Orqestra is a specialized business operations/i)
    ).toBeInTheDocument();
  });

  it('switches to Privacy Policy tab when clicked', () => {
    render(<LegalModal isOpen={true} onClose={vi.fn()} initialDoc="terms" />);

    const privacyTab = screen.getByRole('tab', { name: 'Privacy Policy' });
    fireEvent.click(privacyTab);

    expect(screen.getByRole('heading', { name: 'Privacy Policy' })).toBeInTheDocument();
    expect(
      screen.getByText(/We collect information necessary to provide business operational services/i)
    ).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const handleClose = vi.fn();
    render(<LegalModal isOpen={true} onClose={handleClose} />);

    const closeBtn = screen.getByRole('button', { name: /close legal modal/i });
    fireEvent.click(closeBtn);

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when Close Document footer button is clicked', () => {
    const handleClose = vi.fn();
    render(<LegalModal isOpen={true} onClose={handleClose} />);

    const footerCloseBtn = screen.getByRole('button', { name: /close document/i });
    fireEvent.click(footerCloseBtn);

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('closes on Escape key press', () => {
    const handleClose = vi.fn();
    render(<LegalModal isOpen={true} onClose={handleClose} />);

    fireEvent.keyDown(window, { key: 'Escape' });

    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('displays legitimate support and privacy contact emails', () => {
    render(<LegalModal isOpen={true} onClose={vi.fn()} initialDoc="terms" />);

    const supportLink = screen.getByRole('link', { name: 'support@orqestra.io' });
    expect(supportLink).toHaveAttribute('href', 'mailto:support@orqestra.io');

    const privacyTab = screen.getByRole('tab', { name: 'Privacy Policy' });
    fireEvent.click(privacyTab);

    const privacyLink = screen.getByRole('link', { name: 'privacy@orqestra.io' });
    expect(privacyLink).toHaveAttribute('href', 'mailto:privacy@orqestra.io');
  });
});
