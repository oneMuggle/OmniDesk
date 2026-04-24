import DOMPurify from 'dompurify';

const ALLOWED_TAGS = [
  'b', 'i', 'em', 'strong', 'a', 'p', 'br', 'ul', 'ol', 'li',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'img', 'span', 'div',
  'table', 'thead', 'tbody', 'tr', 'th', 'td', 'blockquote', 'code', 'pre',
];

const ALLOWED_ATTR = ['href', 'alt', 'src', 'title', 'class', 'style', 'target', 'rel'];

/**
 * Sanitize HTML string for safe rendering, preventing XSS attacks.
 * @param {string} html - Raw HTML string to sanitize
 * @returns {string} Sanitized HTML safe for dangerouslySetInnerHTML
 */
export const sanitizeHtml = (html) => {
  if (!html) return '';
  return DOMPurify.sanitize(html, { ALLOWED_TAGS, ALLOWED_ATTR });
};
