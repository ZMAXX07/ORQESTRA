/**
 * Business Onboarding Service
 * Handles client-side validation, authenticated business insertion via Supabase client,
 * duplicate slug detection, and atomic owner-membership verification.
 */

import { supabase, isSupabaseConfigured } from './supabase';
import { isValidCurrencyCode } from '../utils/currencies';

export interface CreateBusinessInput {
  name: string;
  slug?: string;
  currency?: string;
}

export interface CreatedBusiness {
  id: string;
  name: string;
  slug: string | null;
  currency: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface VerifiedMembership {
  id: string;
  business_id: string;
  user_id: string;
  role: string;
  is_active: boolean;
}

export interface OnboardingResult {
  business: CreatedBusiness;
  membership: VerifiedMembership;
}

export class OnboardingError extends Error {
  code: string;
  details?: unknown;

  constructor(message: string, code = 'ONBOARDING_ERROR', details?: unknown) {
    super(message);
    this.name = 'OnboardingError';
    this.code = code;
    this.details = details;
  }
}

/**
 * Generate a clean URL-friendly slug from a business name.
 */
export function generateSlug(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9\s-]/g, '')
    .replace(/[\s_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
}

/**
 * Validate business name boundary constraints.
 */
export function validateBusinessName(name: string): { isValid: boolean; error?: string } {
  const trimmed = name.trim();
  if (!trimmed) {
    return { isValid: false, error: 'Business name is required.' };
  }
  if (trimmed.length < 2) {
    return { isValid: false, error: 'Business name must be at least 2 characters long.' };
  }
  if (trimmed.length > 255) {
    return { isValid: false, error: 'Business name cannot exceed 255 characters.' };
  }
  return { isValid: true };
}

/**
 * Validate workspace slug format and length constraints.
 */
export function validateBusinessSlug(slug: string): { isValid: boolean; error?: string } {
  const trimmed = slug.trim();
  if (!trimmed) {
    return { isValid: true }; // Slug is optional in schema; if omitted, null is stored
  }
  if (trimmed.length < 2) {
    return { isValid: false, error: 'Slug must be at least 2 characters long.' };
  }
  if (trimmed.length > 100) {
    return { isValid: false, error: 'Slug cannot exceed 100 characters.' };
  }
  const slugRegex = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
  if (!slugRegex.test(trimmed)) {
    return {
      isValid: false,
      error: 'Slug must contain only lowercase letters, numbers, and single hyphens without leading or trailing hyphens.',
    };
  }
  return { isValid: true };
}

/**
 * Generate a cryptographically strong UUID v4 identifier.
 */
export function generateUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/**
 * Create a new business workspace using the authenticated Supabase client and verify owner enrollment.
 */
export async function createAndVerifyBusiness(
  input: CreateBusinessInput,
  expectedUserId: string
): Promise<OnboardingResult> {
  if (!isSupabaseConfigured || !supabase) {
    throw new OnboardingError(
      'Supabase client is not configured. Verify frontend environment variables.',
      'UNCONFIGURED'
    );
  }

  if (!expectedUserId || !expectedUserId.trim()) {
    throw new OnboardingError(
      'An authenticated operator session is required to create a business.',
      'UNAUTHENTICATED'
    );
  }

  // 1. Client-boundary validation
  const nameVal = validateBusinessName(input.name);
  if (!nameVal.isValid) {
    throw new OnboardingError(nameVal.error || 'Invalid business name.', 'VALIDATION_ERROR');
  }

  const cleanedSlug = input.slug?.trim() ? input.slug.trim().toLowerCase() : null;
  if (cleanedSlug) {
    const slugVal = validateBusinessSlug(cleanedSlug);
    if (!slugVal.isValid) {
      throw new OnboardingError(slugVal.error || 'Invalid business slug.', 'VALIDATION_ERROR');
    }
  }

  const currency = (input.currency || 'USD').trim().toUpperCase();
  if (!isValidCurrencyCode(currency)) {
    throw new OnboardingError(
      `Unsupported or invalid ISO 4217 currency code "${currency}".`,
      'VALIDATION_ERROR'
    );
  }

  // 2. Perform insert into businesses table via PostgREST with explicit client UUID.
  // Note: We intentionally avoid chaining .select() directly on .insert().
  // In PostgreSQL RLS, INSERT ... RETURNING evaluates the table's SELECT policy
  // (businesses_select_member) BEFORE the AFTER INSERT trigger (trg_on_business_created)
  // commits the user's owner membership, causing an erroneous 42501 permission rejection.
  const businessId = generateUUID();

  const { error: insertError } = await supabase
    .from('businesses')
    .insert({
      id: businessId,
      name: input.name.trim(),
      slug: cleanedSlug,
      currency,
      is_active: true,
    });

  if (insertError) {
    // Unique violation (PostgreSQL 23505) on slug or id
    if (
      insertError.code === '23505' ||
      insertError.message?.toLowerCase().includes('unique') ||
      insertError.message?.toLowerCase().includes('slug')
    ) {
      throw new OnboardingError(
        `The workspace slug "${cleanedSlug}" is already taken. Please choose another slug.`,
        'DUPLICATE_SLUG',
        insertError
      );
    }

    // RLS Permission rejection
    if (
      insertError.code === '42501' ||
      insertError.message?.toLowerCase().includes('row-level security')
    ) {
      throw new OnboardingError(
        'Permission denied. You do not have permission to create a business workspace.',
        'PERMISSION_DENIED',
        insertError
      );
    }

    throw new OnboardingError(
      insertError.message || 'Failed to create business workspace. Please try again.',
      insertError.code || 'INSERT_FAILED',
      insertError
    );
  }

  // 3. Verify owner membership assignment created by database trigger trg_on_business_created
  let verifiedMembership: VerifiedMembership | null = null;
  const maxRetries = 5;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    const { data: memberData, error: memberError } = await supabase
      .from('business_members')
      .select('id, business_id, user_id, role, is_active')
      .eq('business_id', businessId)
      .eq('user_id', expectedUserId)
      .single();

    if (!memberError && memberData) {
      if (memberData.role !== 'owner' || !memberData.is_active) {
        throw new OnboardingError(
          'Security verification failed: User was not assigned the required active owner role.',
          'ROLE_VERIFICATION_FAILED'
        );
      }
      verifiedMembership = memberData as VerifiedMembership;
      break;
    }

    if (attempt < maxRetries) {
      // Exponential backoff for trigger execution latency
      await new Promise((resolve) => setTimeout(resolve, attempt * 150));
    }
  }

  if (!verifiedMembership) {
    throw new OnboardingError(
      'Business workspace was created, but owner membership verification could not be confirmed. Please refresh your session.',
      'MEMBERSHIP_TIMEOUT'
    );
  }

  // 4. Fetch confirmed business record (now authorized since caller is confirmed active owner)
  const { data: businessData, error: fetchError } = await supabase
    .from('businesses')
    .select('id, name, slug, currency, is_active, created_at, updated_at')
    .eq('id', businessId)
    .single();

  if (fetchError || !businessData) {
    throw new OnboardingError(
      fetchError?.message || 'Failed to retrieve created business workspace.',
      fetchError?.code || 'FETCH_FAILED',
      fetchError
    );
  }

  const business = businessData as CreatedBusiness;

  return {
    business,
    membership: verifiedMembership,
  };
}
