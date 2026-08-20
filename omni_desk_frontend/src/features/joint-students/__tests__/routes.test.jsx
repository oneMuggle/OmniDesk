import fs from 'fs';
import path from 'path';

const ROOT = process.cwd();

describe('联培生路由注册', () => {
  it('注册 13 条 joint-students 路由', () => {
    const content = fs.readFileSync(path.join(ROOT, 'src/routes/index.jsx'), 'utf8');
    const matches = content.match(/path:\s*["']joint-students[^"']*["']/g) || [];
    expect(matches.length).toBe(13);
  });

  it('lazyImports 注册 9 个 joint-students 页面', () => {
    const content = fs.readFileSync(path.join(ROOT, 'src/routes/lazyImports.js'), 'utf8');
    const imports = content.match(/import\('\.\.\/features\/joint-students\//g) || [];
    expect(imports.length).toBe(9);
  });
});
