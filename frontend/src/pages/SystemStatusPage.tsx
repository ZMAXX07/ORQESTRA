import React from 'react';
import { HealthResponse, BusinessMembership } from '../types/api';
import { Card, CardHeader, CardTitle, CardBody } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { Alert } from '../components/common/Alert';
import { LoadingSpinner } from '../components/feedback/LoadingSpinner';
import { ErrorState } from '../components/feedback/ErrorState';
import {
  CheckIcon,
  RefreshIcon,
  ServerIcon,
  ShieldCheckIcon,
  ClockIcon,
  LayersIcon,
} from '../components/icons/Icons';
import { formatTimestamp, formatUptime } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';
import { useRealtime } from '../context/RealtimeContext';
import './SystemStatusPage.css';

export interface SystemStatusPageProps {
  health: HealthResponse | null;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
  onOpenSignIn?: () => void;
  onOpenOnboarding?: () => void;
}

export const SystemStatusPage: React.FC<SystemStatusPageProps> = ({
  health,
  isLoading,
  error,
  onRefresh,
  onOpenSignIn,
  onOpenOnboarding,
}) => {
  const { user, serverAuth } = useAuth();
  const {
    status: realtimeStatus,
    error: realtimeError,
    activeBusinessId,
    lastReconciledAt,
    reconnect: reconnectRealtime,
  } = useRealtime();
  const userRole = serverAuth?.active_business?.role;
  const isOwnerOrAdmin = Boolean(
    user && (
      userRole === 'owner' ||
      userRole === 'admin' ||
      serverAuth?.memberships?.some((m: BusinessMembership) => m.role === 'owner' || m.role === 'admin') ||
      serverAuth?.user?.role === 'admin' ||
      user?.app_metadata?.role === 'admin' ||
      (!serverAuth?.active_business && (!serverAuth?.memberships || serverAuth.memberships.length === 0))
    )
  );

  return (
    <div className="orq-status-page" data-testid="system-status-page">
      <header className="orq-status-header">
        <div>
          <div className="orq-status-title-wrap">
            <h1 className="orq-status-title">System Status & Diagnostics</h1>
            <Badge variant="info">
              <ShieldCheckIcon size={12} />
              <span>Platform Engineering</span>
            </Badge>
          </div>
          <p className="orq-status-subtitle">
            Authoritative runtime health probe, subsystem telemetry, and security boundary verification.
          </p>
        </div>
        <div className="orq-status-actions">
          <Button
            variant="secondary"
            size="sm"
            onClick={onRefresh}
            isLoading={isLoading}
            aria-label="Refresh health diagnostics"
          >
            <RefreshIcon size={14} />
            <span>Refresh Diagnostics</span>
          </Button>
        </div>
      </header>

      {/* Connection State Feedback */}
      {isLoading && !health && (
        <LoadingSpinner label="Connecting to Orqestra backend health probe..." size="lg" />
      )}

      {error && (
        <ErrorState
          title="Backend Connection Failure"
          message={error}
          onRetry={onRefresh}
          isRetrying={isLoading}
        />
      )}

      {health && isOwnerOrAdmin && (
        <Alert type="success" title="Backend Foundation Connected">
          Successfully verified {health.app_name} v{health.version} running in {health.environment} mode.
        </Alert>
      )}

      {/* Unauthenticated Access Guard */}
      {!user && (
        <section aria-labelledby="section-auth-required">
          <Card>
            <CardHeader>
              <CardTitle id="section-auth-required">Restricted Platform Access</CardTitle>
              <Badge variant="not_connected">Authentication Required</Badge>
            </CardHeader>
            <CardBody>
              <p className="orq-auth-notice">
                System status diagnostics, server telemetry, and architecture inspection are restricted to authenticated operators with administrative privileges. Please sign in to verify system health.
              </p>
              {onOpenSignIn && (
                <div className="orq-auth-actions">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={onOpenSignIn}
                  >
                    <ShieldCheckIcon size={14} />
                    <span>Sign In as Operator</span>
                  </Button>
                </div>
              )}
            </CardBody>
          </Card>
        </section>
      )}

      {/* Non-Admin Role Access Guard */}
      {user && !isOwnerOrAdmin && (
        <section aria-labelledby="section-privilege-required">
          <Card>
            <CardHeader>
              <CardTitle id="section-privilege-required">Administrative Privilege Required</CardTitle>
              <Badge variant="unavailable">Restricted</Badge>
            </CardHeader>
            <CardBody>
              <p className="orq-auth-notice">
                Your authenticated role is <strong>{userRole ?? 'Staff'}</strong>. Subsystem telemetry, server metrics, and architecture boundary verification require Business Owner or Administrator privileges.
              </p>
            </CardBody>
          </Card>
        </section>
      )}

      {/* Operator Technical Context (Authorized Owners/Admins Only) */}
      {user && isOwnerOrAdmin && (
        <section aria-labelledby="section-operator-context">
          <h2 id="section-operator-context" className="orq-section-heading">
            Authentication & Tenant Access State
          </h2>
          <Card>
            <CardHeader>
              <CardTitle>Authenticated Operator Context</CardTitle>
              <Badge variant="operational">Server Verified</Badge>
            </CardHeader>
            <CardBody>
              <div className="orq-auth-grid">
                <div className="orq-auth-item">
                  <span className="orq-auth-label">Operator Subject ID</span>
                  <code className="orq-auth-value">{user.id}</code>
                </div>
                <div className="orq-auth-item">
                  <span className="orq-auth-label">Email Address</span>
                  <span className="orq-auth-value">{user.email ?? 'Not provided'}</span>
                </div>
                <div className="orq-auth-item">
                  <span className="orq-auth-label">Active Business Context</span>
                  <span className="orq-auth-value">
                    {serverAuth?.active_business ? (
                      <strong>{serverAuth.active_business.business_name}</strong>
                    ) : (
                      'No active business assigned'
                    )}
                  </span>
                </div>
                <div className="orq-auth-item">
                  <span className="orq-auth-label">Business Role</span>
                  <span className="orq-auth-value">
                    {serverAuth?.active_business ? (
                      <Badge variant="info">
                        {serverAuth.active_business.role.toUpperCase()}
                      </Badge>
                    ) : (
                      <Badge variant="neutral">None</Badge>
                    )}
                  </span>
                </div>
              </div>

              {!serverAuth?.active_business && onOpenOnboarding && (
                <div className="orq-auth-actions">
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={onOpenOnboarding}
                    data-testid="onboarding-trigger-btn"
                  >
                    <span>Create Your Business</span>
                    <span aria-hidden="true">→</span>
                  </Button>
                </div>
              )}
            </CardBody>
          </Card>
        </section>
      )}

      {/* Live Runtime Metrics Grid (Authorized Owners/Admins Only) */}
      {health && isOwnerOrAdmin && (
        <section aria-labelledby="section-runtime-diagnostics">
          <h2 id="section-runtime-diagnostics" className="orq-section-heading">
            Live Runtime Diagnostics
          </h2>
          <div className="orq-metrics-grid">
            <Card>
              <CardBody>
                <div className="orq-metric-label">
                  <ServerIcon size={14} />
                  <span>API Status</span>
                </div>
                <div className="orq-metric-value">
                  <Badge variant={health.status === 'healthy' ? 'operational' : 'degraded'}>
                    {health.status.toUpperCase()}
                  </Badge>
                </div>
                <div className="orq-metric-footer">
                  Environment: <code>{health.environment}</code>
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <div className="orq-metric-label">
                  <ClockIcon size={14} />
                  <span>Backend Uptime</span>
                </div>
                <div className="orq-metric-value">
                  {formatUptime(health.uptime_seconds)}
                </div>
                <div className="orq-metric-footer">
                  Active process lifetime
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <div className="orq-metric-label">
                  <LayersIcon size={14} />
                  <span>Timestamp</span>
                </div>
                <div className="orq-metric-value orq-metric-value--sm">
                  {formatTimestamp(health.timestamp)}
                </div>
                <div className="orq-metric-footer">
                  ISO UTC verification probe
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardBody>
                <div className="orq-metric-label">
                  <RefreshIcon size={14} />
                  <span>Realtime Live Sync</span>
                </div>
                <div className="orq-metric-value">
                  <Badge
                    variant={
                      realtimeStatus === 'connected'
                        ? 'operational'
                        : realtimeStatus === 'connecting'
                        ? 'info'
                        : 'degraded'
                    }
                  >
                    {realtimeStatus.toUpperCase()}
                  </Badge>
                </div>
                <div className="orq-metric-footer">
                  {realtimeError ? (
                    <span style={{ color: 'var(--color-danger-text)' }}>{realtimeError}</span>
                  ) : activeBusinessId ? (
                    <span>Channel: <code>{`business:${activeBusinessId.slice(0, 8)}...`}</code></span>
                  ) : (
                    <span>Postgres replication subscription</span>
                  )}
                </div>
                {realtimeStatus !== 'connected' && (
                  <div style={{ marginTop: '8px' }}>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={reconnectRealtime}
                    >
                      <RefreshIcon size={12} />
                      <span>Reconnect Realtime</span>
                    </Button>
                  </div>
                )}
              </CardBody>
            </Card>
          </div>
        </section>
      )}

      {/* Subsystem Component Status Table (Authorized Owners/Admins Only) */}
      {health && isOwnerOrAdmin && (
        <section aria-labelledby="section-component-status">
          <Card>
            <CardHeader>
              <CardTitle id="section-component-status">Verified Component Status</CardTitle>
              <span className="orq-table-summary">
                {Object.keys(health.components || {}).length + 1} inspected subsystems
              </span>
            </CardHeader>
            <CardBody>
              <div className="orq-component-table-wrapper">
                <table className="orq-component-table">
                  <thead>
                    <tr>
                      <th scope="col">Subsystem</th>
                      <th scope="col">State</th>
                      <th scope="col">Diagnostic Details</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(health.components || {}).map(([key, item]) => (
                      <tr key={key}>
                        <td className="orq-component-name">
                          <code>{key}</code>
                        </td>
                        <td>
                          <Badge variant={item.status}>
                            {item.status.replace('_', ' ')}
                          </Badge>
                        </td>
                        <td className="orq-component-details">
                          {item.details}
                        </td>
                      </tr>
                    ))}
                    <tr key="realtime_sync">
                      <td className="orq-component-name">
                        <code>realtime_sync</code>
                      </td>
                      <td>
                        <Badge
                          variant={
                            realtimeStatus === 'connected'
                              ? 'operational'
                              : realtimeStatus === 'connecting'
                              ? 'info'
                              : 'degraded'
                          }
                        >
                          {realtimeStatus === 'connected'
                            ? 'operational'
                            : realtimeStatus === 'connecting'
                            ? 'connecting'
                            : 'disconnected'}
                        </Badge>
                      </td>
                      <td className="orq-component-details">
                        {realtimeStatus === 'connected'
                          ? `Supabase Realtime WebSocket channel active (reconciled ${
                              lastReconciledAt ? formatTimestamp(lastReconciledAt.toISOString()) : 'recently'
                            })`
                          : realtimeError
                          ? `Realtime synchronization degraded: ${realtimeError}`
                          : 'Realtime replication disconnected. Standing by for active business channel.'}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </CardBody>
          </Card>
        </section>
      )}

      {/* Architecture & Implementation Boundaries (Authorized Owners/Admins Only) */}
      {isOwnerOrAdmin && (
        <section aria-labelledby="section-boundaries-title">
          <h2 id="section-boundaries-title" className="orq-section-heading">
            Architecture & Implementation Boundaries
          </h2>
        <div className="orq-boundaries-grid">
          <Card>
            <CardHeader>
              <CardTitle>Phase 1 through Phase 5.2 (Implemented & Verified)</CardTitle>
              <Badge variant="operational">Complete</Badge>
            </CardHeader>
            <CardBody>
              <ul className="orq-boundary-list">
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>FastAPI application with health probe, auth, operations, AI intake, and invoice streaming</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Supabase PostgreSQL schema: 11 core tables with UUIDs, numeric currency, and pinned search_path</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Non-recursive Row Level Security (RLS) with Security Definer helper functions</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Atomic stock operations: <code>adjust_stock_atomic</code>, <code>approve_order_atomic</code>, <code>cancel_order_atomic</code></span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Supabase Realtime live subscriptions with automated heartbeat reconciliation</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>AI-assisted order intake with advisory confidence scoring and human approval gate</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Atomic invoice sequencing, immutable JSONB snapshots, and verifiable ReportLab PDF generation</span>
                </li>
              </ul>
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Phase 6 Quality Hardening (Active)</CardTitle>
              <Badge variant="info">Hardening Active</Badge>
            </CardHeader>
            <CardBody>
              <ul className="orq-boundary-list">
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Operational dashboard powered exclusively by authoritative backend API endpoints</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Consistent pagination, loading, empty, and retry recovery across all tables</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Duplicate submission prevention and in-flight mutation protection</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Seamless multi-module workflow transitions between catalog, inventory, orders, AI, and invoices</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Strict backend JWT token verification and multi-tenant boundary enforcement</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Route-level code splitting with optimized bundle loading and lazy components</span>
                </li>
                <li>
                  <CheckIcon size={14} className="orq-icon-success" />
                  <span>Cross-device responsive layout verification across desktop, tablet, and mobile viewports</span>
                </li>
              </ul>
            </CardBody>
          </Card>
        </div>
      </section>
      )}
    </div>
  );
};
