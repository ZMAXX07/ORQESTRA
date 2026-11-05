/**
 * Typed response schemas representing Orqestra backend health and status.
 */

export type OperationalState =
  | 'operational'
  | 'degraded'
  | 'not_connected'
  | 'connected'
  | 'not_configured'
  | 'unavailable'
  | 'error';

export type SystemHealthStatus = 'healthy' | 'degraded' | 'unhealthy';

export interface ComponentStatus {
  status: OperationalState;
  details: string;
}

export interface HealthResponse {
  status: SystemHealthStatus;
  app_name: string;
  version: string;
  environment: string;
  timestamp: string;
  uptime_seconds: number;
  components: Record<string, ComponentStatus>;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: unknown;
}

export interface ApiErrorResponse {
  error: ApiErrorDetail;
}

export type AppRole = 'owner' | 'admin' | 'staff';

export interface AuthenticatedUser {
  user_id: string;
  email?: string;
  role?: string;
}

export interface BusinessMembership {
  business_id: string;
  business_name: string;
  role: AppRole;
  is_active: boolean;
  currency?: string;
}

export interface AuthContextResponse {
  status: 'authenticated';
  user: AuthenticatedUser;
  active_business?: BusinessMembership;
  memberships: BusinessMembership[];
}

