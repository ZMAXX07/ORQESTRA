import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import {
  validateBusinessName,
  validateBusinessSlug,
  generateSlug,
  createAndVerifyBusiness,
  OnboardingError,
} from '../src/services/onboarding';
import { CreateBusinessModal } from '../src/components/onboarding/CreateBusinessModal';
import { AuthContext, AuthContextValue } from '../src/context/AuthContext';
import { Session, User } from '@supabase/supabase-js';
import * as supabaseModule from '../src/services/supabase';

describe('Phase 8.1A: Operator Onboarding & Business Creation', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  describe('1. Boundary Validation & Slug Utilities', () => {
    it('validates business name constraints (2 to 255 characters, required)', () => {
      expect(validateBusinessName('').isValid).toBe(false);
      expect(validateBusinessName('   ').isValid).toBe(false);
      expect(validateBusinessName('A').isValid).toBe(false);
      expect(validateBusinessName('A'.repeat(256)).isValid).toBe(false);

      expect(validateBusinessName('Acme Corp').isValid).toBe(true);
      expect(validateBusinessName('AB').isValid).toBe(true);
      expect(validateBusinessName('A'.repeat(255)).isValid).toBe(true);
    });

    it('validates workspace slug constraints (optional, lowercase alphanumeric with single hyphens)', () => {
      // Optional slug (empty is allowed)
      expect(validateBusinessSlug('').isValid).toBe(true);
      expect(validateBusinessSlug('   ').isValid).toBe(true);

      // Invalid slugs
      expect(validateBusinessSlug('A').isValid).toBe(false); // too short (< 2)
      expect(validateBusinessSlug('Acme-Corp').isValid).toBe(false); // uppercase
      expect(validateBusinessSlug('acme--corp').isValid).toBe(false); // double hyphen
      expect(validateBusinessSlug('-acmecorp').isValid).toBe(false); // leading hyphen
      expect(validateBusinessSlug('acmecorp-').isValid).toBe(false); // trailing hyphen
      expect(validateBusinessSlug('acme corp').isValid).toBe(false); // space
      expect(validateBusinessSlug('acme_corp').isValid).toBe(false); // underscore
      expect(validateBusinessSlug('a'.repeat(101)).isValid).toBe(false); // too long (> 100)

      // Valid slugs
      expect(validateBusinessSlug('acme').isValid).toBe(true);
      expect(validateBusinessSlug('acme-corp').isValid).toBe(true);
      expect(validateBusinessSlug('alpha-123-beta').isValid).toBe(true);
    });

    it('generates clean URL-friendly slugs from company names', () => {
      expect(generateSlug('Acme Corporation!')).toBe('acme-corporation');
      expect(generateSlug('  Northwind & Sons Supply Co. ')).toBe('northwind-sons-supply-co');
      expect(generateSlug('Tech123 Labs')).toBe('tech123-labs');
      expect(generateSlug('---Multiple---Dashes---')).toBe('multiple-dashes');
    });
  });

  describe('2. createAndVerifyBusiness Service', () => {
    const mockUserId = 'usr_test_operator_001';

    it('guards against unauthenticated calls without user ID', async () => {
      await expect(
        createAndVerifyBusiness({ name: 'Acme' }, '')
      ).rejects.toThrow(/authenticated operator session is required/i);
    });

    it('guards against invalid business names', async () => {
      await expect(
        createAndVerifyBusiness({ name: '' }, mockUserId)
      ).rejects.toThrow(/business name is required/i);
    });

    it('guards against unconfigured Supabase client', async () => {
      vi.spyOn(supabaseModule, 'supabase', 'get').mockReturnValue(null);
      await expect(
        createAndVerifyBusiness({ name: 'Valid Name' }, mockUserId)
      ).rejects.toThrow(/supabase client is not configured/i);
    });

    it('successfully creates business and verifies owner role assignment', async () => {
      const mockBusiness = {
        id: 'biz_new_123',
        name: 'Apex Manufacturing',
        slug: 'apex-mfg',
        currency: 'USD',
        is_active: true,
        created_at: '2026-10-23T12:00:00Z',
        updated_at: '2026-10-23T12:00:00Z',
      };

      const mockMembership = {
        id: 'mem_owner_456',
        business_id: 'biz_new_123',
        user_id: mockUserId,
        role: 'owner',
        is_active: true,
      };

      const mockInsertBusiness = vi.fn().mockResolvedValue({ error: null });

      const mockSingleMember = vi.fn().mockResolvedValue({ data: mockMembership, error: null });
      const mockEqUser = vi.fn().mockReturnValue({ single: mockSingleMember });
      const mockEqBusinessMember = vi.fn().mockReturnValue({ eq: mockEqUser });
      const mockSelectMember = vi.fn().mockReturnValue({ eq: mockEqBusinessMember });

      const mockSingleBusiness = vi.fn().mockResolvedValue({ data: mockBusiness, error: null });
      const mockEqBusiness = vi.fn().mockReturnValue({ single: mockSingleBusiness });
      const mockSelectBusiness = vi.fn().mockReturnValue({ eq: mockEqBusiness });

      const mockClient = {
        from: vi.fn((table: string) => {
          if (table === 'businesses') {
            return {
              insert: mockInsertBusiness,
              select: mockSelectBusiness,
            };
          }
          if (table === 'business_members') {
            return { select: mockSelectMember };
          }
          throw new Error(`Unexpected table: ${table}`);
        }),
      };

      vi.spyOn(supabaseModule, 'supabase', 'get').mockReturnValue(mockClient as any);
      vi.spyOn(supabaseModule, 'isSupabaseConfigured', 'get').mockReturnValue(true);

      const result = await createAndVerifyBusiness(
        { name: 'Apex Manufacturing', slug: 'apex-mfg', currency: 'USD' },
        mockUserId
      );

      expect(mockInsertBusiness).toHaveBeenCalledWith(
        expect.objectContaining({
          name: 'Apex Manufacturing',
          slug: 'apex-mfg',
          currency: 'USD',
          is_active: true,
        })
      );

      expect(result.business.id).toBe('biz_new_123');
      expect(result.membership.role).toBe('owner');
      expect(result.membership.user_id).toBe(mockUserId);
    });

    it('handles duplicate slug errors and throws descriptive OnboardingError', async () => {
      const mockDuplicateError = {
        code: '23505',
        message: 'duplicate key value violates unique constraint "businesses_slug_key"',
      };

      const mockInsertBusiness = vi.fn().mockResolvedValue({ error: mockDuplicateError });
      const mockClient = {
        from: vi.fn().mockReturnValue({ insert: mockInsertBusiness }),
      };

      vi.spyOn(supabaseModule, 'supabase', 'get').mockReturnValue(mockClient as any);
      vi.spyOn(supabaseModule, 'isSupabaseConfigured', 'get').mockReturnValue(true);

      try {
        await createAndVerifyBusiness({ name: 'Acme', slug: 'existing-slug' }, mockUserId);
        expect.unreachable('Should have thrown OnboardingError');
      } catch (err: any) {
        expect(err).toBeInstanceOf(OnboardingError);
        expect(err.code).toBe('DUPLICATE_SLUG');
        expect(err.message).toMatch(/workspace slug "existing-slug" is already taken/i);
      }
    });

    it('handles RLS permission errors properly', async () => {
      const mockRlsError = {
        code: '42501',
        message: 'new row violates row-level security policy for table "businesses"',
      };

      const mockInsertBusiness = vi.fn().mockResolvedValue({ error: mockRlsError });
      const mockClient = {
        from: vi.fn().mockReturnValue({ insert: mockInsertBusiness }),
      };

      vi.spyOn(supabaseModule, 'supabase', 'get').mockReturnValue(mockClient as any);
      vi.spyOn(supabaseModule, 'isSupabaseConfigured', 'get').mockReturnValue(true);

      try {
        await createAndVerifyBusiness({ name: 'Acme', slug: 'acme' }, mockUserId);
        expect.unreachable('Should have thrown OnboardingError');
      } catch (err: any) {
        expect(err).toBeInstanceOf(OnboardingError);
        expect(err.code).toBe('PERMISSION_DENIED');
        expect(err.message).toMatch(/permission denied/i);
      }
    });

    it('rejects if membership verification detects non-owner role', async () => {
      const mockTamperedMembership = {
        id: 'mem_staff_999',
        business_id: 'biz_compromised_999',
        user_id: mockUserId,
        role: 'staff', // Not owner!
        is_active: true,
      };

      const mockInsertBusiness = vi.fn().mockResolvedValue({ error: null });

      const mockSingleMember = vi.fn().mockResolvedValue({ data: mockTamperedMembership, error: null });
      const mockEqUser = vi.fn().mockReturnValue({ single: mockSingleMember });
      const mockEqBusiness = vi.fn().mockReturnValue({ eq: mockEqUser });
      const mockSelectMember = vi.fn().mockReturnValue({ eq: mockEqBusiness });

      const mockClient = {
        from: vi.fn((table: string) => {
          if (table === 'businesses') return { insert: mockInsertBusiness };
          if (table === 'business_members') return { select: mockSelectMember };
          return {};
        }),
      };

      vi.spyOn(supabaseModule, 'supabase', 'get').mockReturnValue(mockClient as any);
      vi.spyOn(supabaseModule, 'isSupabaseConfigured', 'get').mockReturnValue(true);

      await expect(
        createAndVerifyBusiness({ name: 'Compromised LLC' }, mockUserId)
      ).rejects.toThrow(/Security verification failed.*owner role/i);
    });

    it('verifies owner membership is strictly bound to expectedUserId without caller substitution', async () => {
      const wrongUserId = 'usr_impersonator_999';

      const mockInsertBusiness = vi.fn().mockResolvedValue({ error: null });
      // When queried with expectedUserId, no membership is found because trigger used authentic session UID
      const mockSingleMember = vi.fn().mockResolvedValue({ data: null, error: { message: 'Row not found' } });
      const mockEqUser = vi.fn().mockReturnValue({ single: mockSingleMember });
      const mockEqBusiness = vi.fn().mockReturnValue({ eq: mockEqUser });
      const mockSelectMember = vi.fn().mockReturnValue({ eq: mockEqBusiness });

      const mockClient = {
        from: vi.fn((table: string) => {
          if (table === 'businesses') return { insert: mockInsertBusiness };
          if (table === 'business_members') return { select: mockSelectMember };
          return {};
        }),
      };

      vi.spyOn(supabaseModule, 'supabase', 'get').mockReturnValue(mockClient as any);
      vi.spyOn(supabaseModule, 'isSupabaseConfigured', 'get').mockReturnValue(true);

      await expect(
        createAndVerifyBusiness({ name: 'Impersonation Attempt' }, wrongUserId)
      ).rejects.toThrow(/membership verification could not be confirmed/i);
    });
  });

  describe('3. CreateBusinessModal UI Component', () => {
    const mockAuthContext: AuthContextValue = {
      user: { id: 'usr_operator_123', email: 'operator@orqestra.io' } as User,
      session: { access_token: 'valid_jwt_mock' } as Session,
      serverAuth: {
        status: 'authenticated',
        user: { user_id: 'usr_operator_123', email: 'operator@orqestra.io' },
        memberships: [],
      },
      isLoading: false,
      isConfigured: true,
      authError: null,
      signIn: vi.fn(),
      signOut: vi.fn(),
      refreshServerAuth: vi.fn().mockResolvedValue(undefined),
    };

    it('does not render when isOpen is false', () => {
      render(
        <AuthContext.Provider value={mockAuthContext}>
          <CreateBusinessModal isOpen={false} onSuccess={vi.fn()} />
        </AuthContext.Provider>
      );

      expect(screen.queryByTestId('create-business-modal')).not.toBeInTheDocument();
    });

    it('renders modal dialog with accessible attributes, fields, and auto-generated slug', () => {
      render(
        <AuthContext.Provider value={mockAuthContext}>
          <CreateBusinessModal isOpen={true} onSuccess={vi.fn()} />
        </AuthContext.Provider>
      );

      const modal = screen.getByTestId('create-business-modal');
      expect(modal).toBeInTheDocument();
      expect(modal).toHaveAttribute('role', 'dialog');
      expect(modal).toHaveAttribute('aria-modal', 'true');

      expect(screen.getByText('Create Your Business')).toBeInTheDocument();
      expect(screen.getByLabelText(/Business Legal \/ Operating Name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Workspace Slug/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Primary Operating Currency/i)).toBeInTheDocument();

      const nameInput = screen.getByTestId('biz-name-input');
      const slugInput = screen.getByTestId('biz-slug-input');

      // Auto-generates slug from name as user types
      fireEvent.change(nameInput, { target: { value: 'Delta Logistics Inc' } });
      expect(slugInput).toHaveValue('delta-logistics-inc');
    });

    it('allows custom manual slug without overriding when editing name', () => {
      render(
        <AuthContext.Provider value={mockAuthContext}>
          <CreateBusinessModal isOpen={true} onSuccess={vi.fn()} />
        </AuthContext.Provider>
      );

      const nameInput = screen.getByTestId('biz-name-input');
      const slugInput = screen.getByTestId('biz-slug-input');

      fireEvent.change(nameInput, { target: { value: 'Delta Logistics' } });
      expect(slugInput).toHaveValue('delta-logistics');

      // User types custom slug
      fireEvent.change(slugInput, { target: { value: 'delta-fleet' } });
      expect(slugInput).toHaveValue('delta-fleet');

      // Modifying name does not overwrite custom slug
      fireEvent.change(nameInput, { target: { value: 'Delta Logistics Global' } });
      expect(slugInput).toHaveValue('delta-fleet');
    });

    it('displays client validation errors for empty or invalid names', async () => {
      render(
        <AuthContext.Provider value={mockAuthContext}>
          <CreateBusinessModal isOpen={true} onSuccess={vi.fn()} />
        </AuthContext.Provider>
      );

      const submitBtn = screen.getByTestId('create-biz-submit-btn');
      expect(submitBtn).toBeDisabled();

      const nameInput = screen.getByTestId('biz-name-input');
      fireEvent.change(nameInput, { target: { value: ' ' } });
      expect(submitBtn).toBeDisabled();
    });

    it('handles successful business creation, status progress, and triggers onSuccess', async () => {
      const mockSuccess = vi.fn();
      const mockRefresh = vi.fn().mockResolvedValue(undefined);

      const mockBusiness = {
        id: 'biz_created_777',
        name: 'Summit Industrial',
        slug: 'summit-ind',
        currency: 'USD',
        is_active: true,
        created_at: '2026-10-23T12:00:00Z',
        updated_at: '2026-10-23T12:00:00Z',
      };

      const mockMembership = {
        id: 'mem_owner_777',
        business_id: 'biz_created_777',
        user_id: 'usr_operator_123',
        role: 'owner',
        is_active: true,
      };

      const mockSingleBusiness = vi.fn().mockResolvedValue({ data: mockBusiness, error: null });
      const mockEqBusiness = vi.fn().mockReturnValue({ single: mockSingleBusiness });
      const mockSelectBusiness = vi.fn().mockReturnValue({ eq: mockEqBusiness });
      const mockInsertBusiness = vi.fn().mockResolvedValue({ error: null });

      const mockSingleMember = vi.fn().mockResolvedValue({ data: mockMembership, error: null });
      const mockEqUser = vi.fn().mockReturnValue({ single: mockSingleMember });
      const mockEqMemberBusiness = vi.fn().mockReturnValue({ eq: mockEqUser });
      const mockSelectMember = vi.fn().mockReturnValue({ eq: mockEqMemberBusiness });

      const mockClient = {
        from: vi.fn((table: string) => {
          if (table === 'businesses') return { insert: mockInsertBusiness, select: mockSelectBusiness };
          if (table === 'business_members') return { select: mockSelectMember };
          return {};
        }),
      };

      vi.spyOn(supabaseModule, 'supabase', 'get').mockReturnValue(mockClient as any);
      vi.spyOn(supabaseModule, 'isSupabaseConfigured', 'get').mockReturnValue(true);

      render(
        <AuthContext.Provider value={{ ...mockAuthContext, refreshServerAuth: mockRefresh }}>
          <CreateBusinessModal isOpen={true} onSuccess={mockSuccess} />
        </AuthContext.Provider>
      );

      const nameInput = screen.getByTestId('biz-name-input');
      fireEvent.change(nameInput, { target: { value: 'Summit Industrial' } });

      const submitBtn = screen.getByTestId('create-biz-submit-btn');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(mockSuccess).toHaveBeenCalledWith(
          expect.objectContaining({
            business: expect.objectContaining({ id: 'biz_created_777' }),
            membership: expect.objectContaining({ role: 'owner' }),
          })
        );
      });

      expect(mockRefresh).toHaveBeenCalled();
    });

    it('renders duplicate slug error in the field alert when conflict occurs', async () => {
      const mockDuplicateError = {
        code: '23505',
        message: 'duplicate key value violates unique constraint "businesses_slug_key"',
      };

      const mockInsertBusiness = vi.fn().mockResolvedValue({ error: mockDuplicateError });

      const mockClient = {
        from: vi.fn().mockReturnValue({ insert: mockInsertBusiness }),
      };

      vi.spyOn(supabaseModule, 'supabase', 'get').mockReturnValue(mockClient as any);
      vi.spyOn(supabaseModule, 'isSupabaseConfigured', 'get').mockReturnValue(true);

      render(
        <AuthContext.Provider value={mockAuthContext}>
          <CreateBusinessModal isOpen={true} onSuccess={vi.fn()} />
        </AuthContext.Provider>
      );

      const nameInput = screen.getByTestId('biz-name-input');
      fireEvent.change(nameInput, { target: { value: 'Duplicate Company' } });

      const submitBtn = screen.getByTestId('create-biz-submit-btn');
      fireEvent.click(submitBtn);

      await waitFor(() => {
        expect(screen.getAllByText(/already taken/i).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('allows signing out directly from the onboarding modal', () => {
      const mockSignOut = vi.fn();
      render(
        <AuthContext.Provider value={mockAuthContext}>
          <CreateBusinessModal isOpen={true} onSuccess={vi.fn()} onSignOut={mockSignOut} />
        </AuthContext.Provider>
      );

      const signOutBtn = screen.getByRole('button', { name: /Sign Out/i });
      fireEvent.click(signOutBtn);
      expect(mockSignOut).toHaveBeenCalled();
    });
  });
});
