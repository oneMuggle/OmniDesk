import { sanitizeHtml } from './sanitizeHtml';

describe('sanitizeHtml', () => {
  it('returns empty string for empty input', () => {
    expect(sanitizeHtml('')).toBe('');
    expect(sanitizeHtml(null)).toBe('');
    expect(sanitizeHtml(undefined)).toBe('');
  });

  it('returns plain HTML unchanged', () => {
    expect(sanitizeHtml('<p>Hello</p>')).toBe('<p>Hello</p>');
  });

  it('removes script tags', () => {
    const result = sanitizeHtml('<p>Hello</p><script>alert(1)</script>');
    expect(result).toBe('<p>Hello</p>');
  });

  it('removes disallowed tags like button', () => {
    const result = sanitizeHtml('<button onclick="alert(1)">Click</button>');
    expect(result).toBe('Click');
  });

  it('allows allowed attributes', () => {
    const result = sanitizeHtml('<a href="https://example.com" title="Link">Link</a>');
    expect(result).toBe('<a href="https://example.com" title="Link">Link</a>');
  });

  it('allows allowed tags', () => {
    const result = sanitizeHtml('<h1>Title</h1><p>Text</p>');
    expect(result).toBe('<h1>Title</h1><p>Text</p>');
  });
});
