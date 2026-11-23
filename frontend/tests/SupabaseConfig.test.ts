import { describe, it, expect, vi, beforeEach } from 'vitest';

describe('Supabase Client Configuration (Phase 7.3)', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  it('configures client when VITE_SUPABASE_PUBLISHABLE_KEY is provided', async () => {
    vi.stubEnv('VITE_SUPABASE_URL', 'https://vclkeubwpiyhuvprvngx.supabase.co');
    vi.stubEnv('VITE_SUPABASE_PUBLISHABLE_KEY', 'sb_publishable_test_token_123');

    const { isSupabaseConfigured, supabase } = await import('../src/services/supabase');

    expect(isSupabaseConfigured).toBe(true);
    expect(supabase).not.toBeNull();
  });

  it('configures client with fallback to VITE_SUPABASE_ANON_KEY when publishable key is not set', async () => {
    vi.stubEnv('VITE_SUPABASE_URL', 'https://vclkeubwpiyhuvprvngx.supabase.co');
    vi.stubEnv('VITE_SUPABASE_ANON_KEY', 'sb_anon_fallback_key_456');

    const { isSupabaseConfigured, supabase } = await import('../src/services/supabase');

    expect(isSupabaseConfigured).toBe(true);
    expect(supabase).not.toBeNull();
  });

  it('evaluates isSupabaseConfigured to false when keys are missing', async () => {
    vi.stubEnv('VITE_SUPABASE_URL', '');
    vi.stubEnv('VITE_SUPABASE_PUBLISHABLE_KEY', '');
    vi.stubEnv('VITE_SUPABASE_ANON_KEY', '');

    const { isSupabaseConfigured, supabase } = await import('../src/services/supabase');

    expect(isSupabaseConfigured).toBe(false);
    expect(supabase).toBeNull();
  });
});
