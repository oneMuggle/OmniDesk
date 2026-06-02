/**
 * Formatting utilities for consistent display across the app.
 */

/**
 * Format a date string or Date object to a localized date string.
 */
export function formatDate(date) {
  if (!date) return '';
  return new Date(date).toLocaleDateString();
}

/**
 * Truncate text to a maximum length and append ellipsis.
 */
export function truncateText(text, maxLength = 50) {
  if (!text || text.length <= maxLength) return text || '';
  return text.slice(0, maxLength) + '...';
}
