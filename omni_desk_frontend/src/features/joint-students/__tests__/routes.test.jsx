/* global process */
import fs from 'fs';
import path from 'path';

const ROOT = process.cwd();

describe('联培生路由注册', () => {
  it('注册 13 条 joint-students 路由', () => {
    const content = fs.readFileSync(path.join(ROOT, 'src/routes/index.jsx'), 'utf8');
    const matches = content.match(/path:\s*["']joint-students[^"']*["']/g) || [];
    expect(matches.length).toBe(13);
  });

  it('动态详情和编辑路由使用独立稳定权限键', () => {
    const content = fs.readFileSync(path.join(ROOT, 'src/routes/index.jsx'), 'utf8');
    expect(content).toContain('path: "joint-students/admin/students/:id/edit"');
    expect(content).toContain('pagePath="/joint-students/admin/students/:id"');
    expect(content).toContain('pagePath="/joint-students/admin/students/:id/edit"');
  });

  it('学生/导师/管理员/专家路由均配置 pagePath', () => {
    const content = fs.readFileSync(path.join(ROOT, 'src/routes/index.jsx'), 'utf8');
    expect(content).toContain('pagePath="/joint-students/student/reports"');
    expect(content).toContain('pagePath="/joint-students/student/stipends"');
    expect(content).toContain('pagePath="/joint-students/mentor/overview"');
  });

  it('lazyImports 注册 9 个 joint-students 页面', () => {
    const content = fs.readFileSync(path.join(ROOT, 'src/routes/lazyImports.js'), 'utf8');
    const imports = content.match(/import\('\.\.\/features\/joint-students\//g) || [];
    expect(imports.length).toBe(9);
  });
});
