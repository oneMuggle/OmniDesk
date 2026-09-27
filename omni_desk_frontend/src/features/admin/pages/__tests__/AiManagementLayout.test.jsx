import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import AiManagementLayout from '../AiManagementLayout';
import AiManagementIndex from '../../components/AiManagementIndex';
import { useAuth } from '../../../auth/context/AuthContext';
import {
  ADMIN_INDEX_CANDIDATES,
  getAdminRoutePermissions,
  requiredForAdminRoute,
} from '../../config/adminRoutePermissions';

jest.mock('../../../auth/context/AuthContext', () => ({
  __esModule: true,
  useAuth: jest.fn(),
}));

const mockPermissions = (granted) => {
  useAuth.mockReturnValue({
    hasPermission: (required) => [].concat(required).some((p) => granted.includes(p)),
  });
};

const Where = () => <div data-testid="page">{useLocation().pathname}</div>;

const renderAt = (url) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/control-panel/ai" element={<AiManagementLayout />}>
          <Route index element={<AiManagementIndex />} />
          <Route path="*" element={<Where />} />
        </Route>
        <Route path="/unauthorized" element={<div>Unauthorized Page</div>} />
      </Routes>
    </MemoryRouter>
  );

describe('AiManagementLayout(S2-2 控制台 AI 管理)', () => {
  it('管理员看到三个标签,首页跳到使用统计', () => {
    mockPermissions(['admin']);
    renderAt('/control-panel/ai');
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['使用统计', 'Agent 审计', 'AI 应用配置']);
    expect(screen.getByTestId('page')).toHaveTextContent('/control-panel/ai/stats');
  });

  it('切换标签改变路由', async () => {
    const user = userEvent.setup();
    mockPermissions(['admin']);
    renderAt('/control-panel/ai/stats');
    await user.click(screen.getByRole('tab', { name: 'Agent 审计' }));
    expect(screen.getByTestId('page')).toHaveTextContent('/control-panel/ai/audit');
  });

  it('只有旧审计页授权的用户组只看到审计标签,首页跳到审计', () => {
    mockPermissions(['/control-panel/smart-assistant/audit']);
    renderAt('/control-panel/ai');
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['Agent 审计']);
    expect(screen.getByTestId('page')).toHaveTextContent('/control-panel/ai/audit');
  });

  it('无任何授权时跳到 /unauthorized', () => {
    mockPermissions([]);
    renderAt('/control-panel/ai');
    expect(screen.getByText('Unauthorized Page')).toBeInTheDocument();
  });
});

describe('AI 管理权限配置', () => {
  it('新地址接受管理员与旧页面授权,旧 key 保留', () => {
    expect(getAdminRoutePermissions('ai/stats')).toEqual(['admin', '/smart-assistant/stats']);
    expect(getAdminRoutePermissions('ai/audit')).toEqual(['admin', '/control-panel/smart-assistant/audit']);
    expect(getAdminRoutePermissions('ai/apps')).toEqual(['admin', '/control-panel/ai-apps']);
    expect(requiredForAdminRoute('ai')).toEqual(expect.arrayContaining(['admin', '/control-panel/ai']));
    expect(getAdminRoutePermissions('smart-assistant/audit')).toEqual(['admin']);
    expect(getAdminRoutePermissions('ai-apps')).toEqual(['admin']);
  });

  it('控制台首页候选改为 AI 管理入口', () => {
    expect(ADMIN_INDEX_CANDIDATES).toContain('ai');
    expect(ADMIN_INDEX_CANDIDATES).not.toContain('smart-assistant/audit');
    expect(ADMIN_INDEX_CANDIDATES).not.toContain('ai-apps');
  });
});
