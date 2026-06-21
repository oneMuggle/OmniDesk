import { z } from 'zod';

/** 登录表单 schema。 */
export const LoginSchema = z.object({
    username: z
        .preprocess((v) => (v === undefined || v === null ? '' : v), z.string())
        .pipe(
            z.string().superRefine((val, ctx) => {
                if (val.length < 1) {
                    ctx.addIssue({ code: z.ZodIssueCode.custom, message: '请输入用户名' });
                } else if (val.length < 3) {
                    ctx.addIssue({ code: z.ZodIssueCode.custom, message: '用户名至少 3 字符' });
                } else if (val.length > 64) {
                    ctx.addIssue({ code: z.ZodIssueCode.custom, message: '用户名不超过 64 字符' });
                }
            }),
        ),
    password: z
        .preprocess((v) => (v === undefined || v === null ? '' : v), z.string())
        .pipe(
            z.string().superRefine((val, ctx) => {
                if (val.length < 1) {
                    ctx.addIssue({ code: z.ZodIssueCode.custom, message: '请输入密码' });
                } else if (val.length < 8) {
                    ctx.addIssue({ code: z.ZodIssueCode.custom, message: '密码至少 8 字符' });
                } else if (val.length > 128) {
                    ctx.addIssue({ code: z.ZodIssueCode.custom, message: '密码不超过 128 字符' });
                }
            }),
        ),
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
