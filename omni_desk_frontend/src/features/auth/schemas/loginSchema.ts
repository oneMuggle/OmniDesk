import { z } from 'zod';

/** 登录表单 schema。 */
export const LoginSchema = z.object({
    username: z
        .string()
        .min(3, '用户名至少 3 字符')
        .max(64, '用户名不超过 64 字符'),
    password: z
        .string()
        .min(8, '密码至少 8 字符')
        .max(128, '密码不超过 128 字符'),
});

export type LoginFormValues = z.infer<typeof LoginSchema>;

/** 把 zod 错误转 antd Form 字段错误格式。 */
export function zodToAntdErrors(error: z.ZodError): Record<string, { errors: string[] }> {
    const fieldErrors: Record<string, { errors: string[] }> = {};
    for (const issue of error.issues) {
        const path = issue.path.join('.');
        if (!fieldErrors[path]) {
            fieldErrors[path] = { errors: [] };
        }
        fieldErrors[path].errors.push(issue.message);
    }
    return fieldErrors;
}
