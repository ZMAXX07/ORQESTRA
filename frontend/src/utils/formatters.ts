/**
 * Formatting utilities for system metrics and timestamps.
 * Note: Strictly avoid em dashes in user-facing strings.
 */

export function formatTimestamp(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) {
      return 'Invalid timestamp';
    }
    return new Intl.DateTimeFormat('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short',
    }).format(date);
  } catch {
    return 'Invalid timestamp';
  }
}

export function formatUptime(seconds: number): string {
  if (seconds < 0) return '0s';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  const parts: string[] = [];
  if (hrs > 0) parts.push(`${hrs}h`);
  if (mins > 0 || hrs > 0) parts.push(`${mins}m`);
  parts.push(`${secs}s`);

  return parts.join(' ');
}

export {
  formatCurrency,
  getCurrencySymbol,
  getCurrencyInfo,
  detectUserDefaultCurrency,
  isValidCurrencyCode,
  ISO_CURRENCIES,
} from './currencies';
