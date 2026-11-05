import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { Session, User } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured } from '../services/supabase';
import { fetchAuthMe } from '../services/api';
import { AuthContextResponse } from '../types/api';

export interface SignUpResult {
  success: boolean;
  confirmationRequired?: boolean;
  error?: string;
}

export interface ResetPasswordResult {
  success: boolean;
  error?: string;
}

export interface AuthContextValue {
  session: Session | null;
  user: User | null;
  serverAuth: AuthContextResponse | null;
  isLoading: boolean;
  isConfigured: boolean;
  authError: string | null;
  isRecoveryMode?: boolean;
  setIsRecoveryMode?: (val: boolean) => void;
  signIn: (email: string, pass: string) => Promise<{ success: boolean; error?: string }>;
  signUp?: (email: string, pass: string, fullName?: string) => Promise<SignUpResult>;
  signOut: () => Promise<void>;
  resetPassword?: (email: string) => Promise<ResetPasswordResult>;
  updatePassword?: (newPassword: string) => Promise<{ success: boolean; error?: string }>;
  refreshServerAuth: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [serverAuth, setServerAuth] = useState<AuthContextResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isRecoveryMode, setIsRecoveryMode] = useState<boolean>(false);

  const verifyWithBackend = useCallback(async (token: string) => {
    try {
      const data = await fetchAuthMe(token);
      setServerAuth(data);
      setAuthError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Server authentication verification failed';
      setAuthError(msg);
      setServerAuth(null);
    }
  }, []);

  useEffect(() => {
    // Check if URL indicates password recovery mode
    if (typeof window !== 'undefined') {
      const isRecovery =
        window.location.search.includes('recovery=true') ||
        window.location.hash.includes('type=recovery');
      if (isRecovery) {
        setIsRecoveryMode(true);
      }
    }

    if (!isSupabaseConfigured || !supabase) {
      setIsLoading(false);
      return;
    }

    // 1. Initial session restoration
    supabase.auth.getSession().then(({ data: { session: initialSession }, error }) => {
      if (error) {
        setAuthError(error.message);
      }
      setSession(initialSession);
      setUser(initialSession?.user ?? null);

      // Clean URL fragment once Supabase has consumed the token
      if (typeof window !== 'undefined' && window.location.hash.includes('access_token')) {
        window.history.replaceState(null, '', window.location.pathname + window.location.search);
      }

      if (initialSession?.access_token) {
        verifyWithBackend(initialSession.access_token).finally(() => {
          setIsLoading(false);
        });
      } else {
        setIsLoading(false);
      }
    });

    // 2. Auth state subscription (sign in, sign out, token refresh, password recovery)
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      async (event, currentSession) => {
        setSession(currentSession);
        setUser(currentSession?.user ?? null);

        if (event === 'PASSWORD_RECOVERY') {
          setIsRecoveryMode(true);
        }

        if (event === 'SIGNED_OUT' || !currentSession) {
          setServerAuth(null);
          setAuthError(null);
        } else if (currentSession?.access_token) {
          await verifyWithBackend(currentSession.access_token);
        }
        setIsLoading(false);
      }
    );

    return () => {
      subscription.unsubscribe();
    };
  }, [verifyWithBackend]);

  const signIn = async (email: string, pass: string) => {
    if (!isSupabaseConfigured || !supabase) {
      return {
        success: false,
        error: 'Supabase credentials are not configured in frontend .env.',
      };
    }

    setAuthError(null);
    try {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.trim(),
        password: pass,
      });

      if (error) {
        let msg = error.message;
        if (msg.toLowerCase().includes('invalid login credentials')) {
          msg = 'Invalid email or password. Please verify your credentials and try again.';
        } else if (msg.toLowerCase().includes('email not confirmed')) {
          msg = 'Email address has not been confirmed. Please check your inbox for the verification link.';
        }
        setAuthError(msg);
        return { success: false, error: msg };
      }

      setSession(data.session);
      setUser(data.user);
      if (data.session?.access_token) {
        await verifyWithBackend(data.session.access_token);
      }
      return { success: true };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Sign in failed';
      setAuthError(msg);
      return { success: false, error: msg };
    }
  };

  const signUp = async (
    email: string,
    pass: string,
    fullName?: string
  ): Promise<SignUpResult> => {
    if (!isSupabaseConfigured || !supabase) {
      return {
        success: false,
        error: 'Supabase credentials are not configured in frontend .env.',
      };
    }

    setAuthError(null);
    try {
      const redirectUrl =
        typeof window !== 'undefined' ? `${window.location.origin}/` : undefined;
      const { data, error } = await supabase.auth.signUp({
        email: email.trim(),
        password: pass,
        options: {
          data: {
            full_name: fullName?.trim() || '',
          },
          emailRedirectTo: redirectUrl,
        },
      });

      if (error) {
        let msg = error.message;
        if (msg.toLowerCase().includes('already registered')) {
          msg = 'An account with this email already exists. Please sign in instead.';
        }
        setAuthError(msg);
        return { success: false, error: msg };
      }

      // Check if email confirmation is required (session is null, but user is returned)
      if (data.user && !data.session) {
        return {
          success: true,
          confirmationRequired: true,
        };
      }

      if (data.session) {
        setSession(data.session);
        setUser(data.user);
        if (data.session.access_token) {
          await verifyWithBackend(data.session.access_token);
        }
        return {
          success: true,
          confirmationRequired: false,
        };
      }

      return { success: true, confirmationRequired: false };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Registration failed';
      setAuthError(msg);
      return { success: false, error: msg };
    }
  };

  const signOut = async () => {
    if (!isSupabaseConfigured || !supabase) return;
    try {
      await supabase.auth.signOut();
    } finally {
      setSession(null);
      setUser(null);
      setServerAuth(null);
      setAuthError(null);
      setIsRecoveryMode(false);
    }
  };

  const resetPassword = async (email: string): Promise<ResetPasswordResult> => {
    if (!isSupabaseConfigured || !supabase) {
      return {
        success: false,
        error: 'Supabase credentials are not configured in frontend .env.',
      };
    }

    setAuthError(null);
    try {
      const redirectUrl =
        typeof window !== 'undefined' ? `${window.location.origin}/?recovery=true` : undefined;
      const { error } = await supabase.auth.resetPasswordForEmail(email.trim(), {
        redirectTo: redirectUrl,
      });

      if (error) {
        setAuthError(error.message);
        return { success: false, error: error.message };
      }

      return { success: true };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Password reset request failed';
      setAuthError(msg);
      return { success: false, error: msg };
    }
  };

  const updatePassword = async (
    newPassword: string
  ): Promise<{ success: boolean; error?: string }> => {
    if (!isSupabaseConfigured || !supabase) {
      return {
        success: false,
        error: 'Supabase credentials are not configured in frontend .env.',
      };
    }

    setAuthError(null);
    try {
      const { error } = await supabase.auth.updateUser({
        password: newPassword,
      });

      if (error) {
        setAuthError(error.message);
        return { success: false, error: error.message };
      }

      setIsRecoveryMode(false);
      return { success: true };
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update password';
      setAuthError(msg);
      return { success: false, error: msg };
    }
  };

  const refreshServerAuth = async () => {
    if (session?.access_token) {
      await verifyWithBackend(session.access_token);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        session,
        user,
        serverAuth,
        isLoading,
        isConfigured: isSupabaseConfigured,
        authError,
        isRecoveryMode,
        setIsRecoveryMode,
        signIn,
        signUp,
        signOut,
        resetPassword,
        updatePassword,
        refreshServerAuth,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
