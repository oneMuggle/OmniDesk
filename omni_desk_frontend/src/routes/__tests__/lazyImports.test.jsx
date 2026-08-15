import { render, screen } from '@testing-library/react';
import * as lazyImports from '../lazyImports';
import LazyComponent from '../LazyComponent';

const LAZY_TYPE = Symbol.for('react.lazy');

describe('lazyImports 注册中心', () => {
  it('导出 72 个懒加载页面组件', () => {
    expect(Object.keys(lazyImports)).toHaveLength(72);
  });

  it('每个导出均为 React.lazy 包装组件,且命名无重复', () => {
    const seen = new Set();
    Object.entries(lazyImports).forEach(([name, comp]) => {
      // React.lazy 返回 { $$typeof: Symbol.for('react.lazy'), _payload, _init }
      expect(comp.$$typeof).toBe(LAZY_TYPE);
      expect(seen.has(name)).toBe(false);
      seen.add(name);
    });
    expect(seen.size).toBe(72);
  });
});

describe('LazyComponent', () => {
  it('渲染懒加载组件的子内容', () => {
    render(<LazyComponent component={() => <div>测试页面</div>} />);
    expect(screen.getByText('测试页面')).toBeInTheDocument();
  });
});
