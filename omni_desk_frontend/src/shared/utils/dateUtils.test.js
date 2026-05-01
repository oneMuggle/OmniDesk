import { parseDate, formatDate, isValidDate, toServerFormat, fromServerFormat, isBefore, addDays, validateStartDate, validateEndDate } from './dateUtils';

describe('dateUtils', () => {
  describe('isValidDate', () => {
    it('returns true for valid date string', () => {
      expect(isValidDate('2024-01-01')).toBe(true);
    });

    it('returns true for valid Date object', () => {
      expect(isValidDate(new Date('2024-01-01'))).toBe(true);
    });

    it('returns false for invalid date', () => {
      expect(isValidDate('not-a-date')).toBe(false);
    });

    it('returns null/falsy for null', () => {
      expect(isValidDate(null)).toBeFalsy();
    });
  });

  describe('parseDate', () => {
    it('parses a valid date string', () => {
      const result = parseDate('2024-06-15');
      expect(result).not.toBeNull();
      expect(result.format('YYYY-MM-DD')).toBe('2024-06-15');
    });

    it('returns null for invalid date', () => {
      expect(parseDate('invalid')).toBeNull();
    });

    it('handles dayjs instance', () => {
      const dayjs = require('dayjs');
      const input = dayjs('2024-03-01');
      const result = parseDate(input);
      expect(result.format('YYYY-MM-DD')).toBe('2024-03-01');
    });
  });

  describe('formatDate', () => {
    it('formats date with default format', () => {
      expect(formatDate('2024-01-15')).toBe('2024-01-15');
    });

    it('formats date with custom format', () => {
      expect(formatDate('2024-01-15', 'MM/DD/YYYY')).toBe('01/15/2024');
    });

    it('returns empty string for invalid date', () => {
      expect(formatDate('invalid')).toBe('');
    });
  });

  describe('toServerFormat', () => {
    it('returns ISO format string', () => {
      const result = toServerFormat('2024-01-01');
      expect(result).toMatch(/2024-01-01T/);
    });

    it('returns null for null input', () => {
      expect(toServerFormat(null)).toBeNull();
    });
  });

  describe('fromServerFormat', () => {
    it('parses a server date string', () => {
      const result = fromServerFormat('2024-01-01T00:00:00+08:00');
      expect(result).not.toBeNull();
    });

    it('handles array of dates', () => {
      const result = fromServerFormat(['2024-01-01', '2024-01-02']);
      expect(result).toHaveLength(2);
    });

    it('returns null for null input', () => {
      expect(fromServerFormat(null)).toBeNull();
    });
  });

  describe('isBefore', () => {
    it('returns true when first date is before second', () => {
      expect(isBefore('2024-01-01', '2024-01-02')).toBe(true);
    });

    it('returns false when first date is after second', () => {
      expect(isBefore('2024-01-02', '2024-01-01')).toBe(false);
    });

    it('returns false for invalid dates', () => {
      expect(isBefore('invalid', '2024-01-01')).toBe(false);
    });
  });

  describe('addDays', () => {
    it('adds days to a date', () => {
      const result = addDays('2024-01-01', 5);
      expect(result.format('YYYY-MM-DD')).toBe('2024-01-06');
    });

    it('returns null for invalid date', () => {
      expect(addDays('invalid', 5)).toBeNull();
    });
  });

  describe('validateStartDate', () => {
    it('returns date if valid', () => {
      const result = validateStartDate('2024-01-01');
      expect(result).not.toBeNull();
    });

    it('returns null if invalid', () => {
      expect(validateStartDate('invalid')).toBeNull();
    });
  });

  describe('validateEndDate', () => {
    it('returns date if valid', () => {
      const result = validateEndDate('2024-01-01');
      expect(result).not.toBeNull();
    });

    it('returns null if invalid', () => {
      expect(validateEndDate('invalid')).toBeNull();
    });
  });
});
