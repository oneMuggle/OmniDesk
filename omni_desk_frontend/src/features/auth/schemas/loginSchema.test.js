import { LoginSchema, zodToAntdErrors } from './loginSchema';

describe('LoginSchema', () => {
    test('accepts valid input', () => {
        const result = LoginSchema.safeParse({ username: 'alice', password: 'Pass1234' });
        expect(result.success).toBe(true);
    });

    test('rejects short username', () => {
        const result = LoginSchema.safeParse({ username: 'ab', password: 'Pass1234' });
        expect(result.success).toBe(false);
        if (!result.success) {
            expect(result.error.issues[0].path).toEqual(['username']);
            expect(result.error.issues[0].message).toContain('至少 3 字符');
        }
    });

    test('rejects short password', () => {
        const result = LoginSchema.safeParse({ username: 'alice', password: 'short' });
        expect(result.success).toBe(false);
    });

    test('rejects empty fields', () => {
        const result = LoginSchema.safeParse({ username: '', password: '' });
        expect(result.success).toBe(false);
        expect(result.error.issues.length).toBe(2);
    });

    test('zodToAntdErrors formats errors', () => {
        const result = LoginSchema.safeParse({ username: 'ab', password: 'short' });
        if (result.success) throw new Error('expected failure');
        const formatted = zodToAntdErrors(result.error);
        expect(formatted.username).toBeDefined();
        expect(formatted.password).toBeDefined();
        expect(formatted.username.errors[0]).toContain('至少 3 字符');
    });
});
