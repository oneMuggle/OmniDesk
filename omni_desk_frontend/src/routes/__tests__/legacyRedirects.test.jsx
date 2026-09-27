import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import LegacyRedirect from '../LegacyRedirect';
import router from '..';

jest.mock('../../features/auth/context/AuthContext', () => ({
  __esModule: true,
  useAuth: jest.fn(() => ({ isInitializing: false, isAuthenticated: true, hasPermission: () => true })),
}));

const Where = () => {
  const { pathname, search, hash } = useLocation();
  return <div data-testid="where">{`${pathname}${search}${hash}`}</div>;
};

/** 收集路由配置中所有 LegacyRedirect(含被 ProtectedRoute 包裹的),返回 { 完整旧地址: 新地址 } */
const collectRedirects = (routes, prefix = '') =>
  routes.reduce((acc, route) => {
    const { path, element, children: nested } = route;
    const full = path ? `${prefix.replace(/\/$/, '')}/${path}`.replace(/^\/\//, '/') : prefix;
    const inner = element?.props?.children;
    const target =
      element?.type === LegacyRedirect ? element.props.to
        : inner?.type === LegacyRedirect ? inner.props.to
          : null;
    if (target) acc[full] = target;
    return nested ? { ...acc, ...collectRedirects(nested, full) } : acc;
  }, {});

describe('S2-2 旧 AI 页面地址重定向', () => {
  it('路由表中的重定向与计划一致', () => {
    expect(collectRedirects(router.routes)).toEqual({
      '/control-panel/smart-assistant/audit': '/control-panel/ai/audit',
      '/control-panel/ai-apps': '/control-panel/ai/apps',
      '/smart-assistant/stats': '/control-panel/ai/stats',
      '/ragflow-chat': '/smart-assistant/apps/ragflow',
      '/dify-apps': '/smart-assistant/apps/dify',
      '/dify-apps/:appId': '/smart-assistant/apps/dify/:appId',
      '/office-assistant': '/smart-assistant/apps/office',
      '/file-analysis': '/smart-assistant/apps/file-analysis',
      '/ai-showcase': '/smart-assistant',
    });
  });

  it.each([
    ['/ragflow-chat', '/ragflow-chat', '/smart-assistant/apps/ragflow', '/smart-assistant/apps/ragflow'],
    ['/file-analysis', '/file-analysis?from=menu#top', '/smart-assistant/apps/file-analysis', '/smart-assistant/apps/file-analysis?from=menu#top'],
    ['/dify-apps/:appId', '/dify-apps/42?tab=run', '/smart-assistant/apps/dify/:appId', '/smart-assistant/apps/dify/42?tab=run'],
  ])('%s 跳转并保留参数、查询串和 hash', (pattern, url, to, expected) => {
    render(
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path={pattern} element={<LegacyRedirect to={to} />} />
          <Route path="*" element={<Where />} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByTestId('where')).toHaveTextContent(expected);
  });

  it('智能助手下的应用都挂在 /smart-assistant/apps/* 且带守卫', () => {
    const root = router.routes.find((r) => r.path === '/');
    const { children: mainChildren } = root;
    const assistant = mainChildren.find((r) => r.path === 'smart-assistant');
    const { children: tabs } = assistant;
    const paths = tabs.map((r) => r.path || '(index)');
    expect(paths).toEqual([
      '(index)', 'tasks', 'apps', 'apps/dify', 'apps/dify/:appId', 'apps/ragflow', 'apps/office', 'apps/file-analysis', 'apps/*', 'stats',
    ]);
  });
});
