import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { MemoryRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import SmartAssistantLayout from '../SmartAssistantLayout';
import AssistantAppsPage from '../AssistantAppsPage';
import { ASSISTANT_APPS, activeAssistantTab } from '../assistantNav';

const Where = ({ label }) => {
  const { pathname } = useLocation();
  return <div data-testid="page">{`${label}@${pathname}`}</div>;
};

const renderAt = (url) =>
  render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/smart-assistant" element={<SmartAssistantLayout />}>
          <Route index element={<Where label="chat" />} />
          <Route path="tasks" element={<Where label="tasks" />} />
          <Route path="apps" element={<AssistantAppsPage />} />
          <Route path="apps/ragflow" element={<Where label="ragflow" />} />
          <Route path="apps/*" element={<Navigate to="/smart-assistant/apps" replace />} />
        </Route>
      </Routes>
    </MemoryRouter>
  );

const selectedTab = () => screen.getByRole('tab', { selected: true });

describe('SmartAssistantLayout(S2-2 智能助手统一入口)', () => {
  it('默认显示对话标签', () => {
    renderAt('/smart-assistant');
    expect(selectedTab()).toHaveTextContent('对话');
    expect(screen.getByTestId('page')).toHaveTextContent('chat@/smart-assistant');
  });

  it('切换标签会改变路由', async () => {
    const user = userEvent.setup();
    renderAt('/smart-assistant');
    await user.click(screen.getByRole('tab', { name: '任务' }));
    expect(screen.getByTestId('page')).toHaveTextContent('tasks@/smart-assistant/tasks');
    expect(selectedTab()).toHaveTextContent('任务');
  });

  it('应用子页时「应用」标签处于选中态', () => {
    renderAt('/smart-assistant/apps/ragflow');
    expect(selectedTab()).toHaveTextContent('应用');
    expect(screen.getByTestId('page')).toHaveTextContent('ragflow@/smart-assistant/apps/ragflow');
  });

  it('应用列表展示全部应用,点击进入对应页面', async () => {
    const user = userEvent.setup();
    renderAt('/smart-assistant/apps');
    ASSISTANT_APPS.forEach((app) => {
      expect(screen.getByRole('link', { name: app.title })).toHaveAttribute('href', `/smart-assistant/apps/${app.key}`);
    });
    await user.click(screen.getByRole('link', { name: 'Ragflow 聊天' }));
    expect(screen.getByTestId('page')).toHaveTextContent('ragflow@/smart-assistant/apps/ragflow');
  });

  it('未知应用回到应用列表', () => {
    renderAt('/smart-assistant/apps/unknown');
    expect(screen.getByRole('link', { name: 'Dify 应用' })).toBeInTheDocument();
  });
});

describe('activeAssistantTab', () => {
  it.each([
    ['/smart-assistant', 'chat'],
    ['/smart-assistant/tasks', 'tasks'],
    ['/smart-assistant/apps/dify/3', 'apps'],
  ])('%s -> %s', (pathname, key) => {
    expect(activeAssistantTab(pathname)).toBe(key);
  });
});
