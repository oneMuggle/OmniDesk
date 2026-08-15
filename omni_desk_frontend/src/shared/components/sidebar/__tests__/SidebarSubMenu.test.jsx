import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import SidebarSubMenu from '../SidebarSubMenu';

const item = {
  type: 'submenu',
  text: 'AI 助手',
  icon: () => null,
  permission: null,
  subItems: [
    { to: '/smart-assistant', icon: () => null, text: '智能助手', permission: null },
    { to: '/knowledge-base', text: '知识库管理', permission: 'admin' },
    { to: '/notifications', text: '通知中心', permission: null, badgeCount: 3 },
  ],
};

const baseProps = {
  item,
  isCollapsed: false,
  isMobileMenuOpen: false,
  location: { pathname: '/smart-assistant' },
  hasPermission: () => true,
  expandedSubMenu: {},
  collapsedPopoverOpen: null,
  onToggleSubMenu: jest.fn(),
  onCollapsedPopoverChange: jest.fn(),
  onCloseMobile: jest.fn(),
};

const renderSubMenu = (props) => render(
  <MemoryRouter>
    <SidebarSubMenu {...baseProps} {...props} />
  </MemoryRouter>
);

describe('SidebarSubMenu', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('expanded 态渲染全部子项（hasPermission 全通过）', () => {
    renderSubMenu();
    expect(screen.getByText('AI 助手')).toBeInTheDocument();
    expect(screen.getByText('智能助手')).toBeInTheDocument();
    expect(screen.getByText('知识库管理')).toBeInTheDocument();
    expect(screen.getByText('通知中心')).toBeInTheDocument();
  });

  it('expanded 态按权限过滤子项', () => {
    renderSubMenu({ hasPermission: (perm) => perm === null });
    expect(screen.getByText('智能助手')).toBeInTheDocument();
    expect(screen.queryByText('知识库管理')).not.toBeInTheDocument(); // admin 被过滤
  });

  it('badgeCount 大于 0 时渲染 Badge 数字', () => {
    renderSubMenu();
    expect(screen.getByText('3')).toBeInTheDocument(); // 通知中心 badgeCount=3
  });

  it('collapsed 态点击 header 触发 onCollapsedPopoverChange 函数式更新', () => {
    renderSubMenu({ isCollapsed: true });
    // collapsed 态 header 唯一带 aria-haspopup=true（子项 Link 无此属性）
    fireEvent.click(screen.getByRole('menuitem', { haspopup: true }));
    expect(baseProps.onCollapsedPopoverChange).toHaveBeenCalledTimes(1);
    // 参数应为函数式 setState（prev => prev === text ? null : text）
    const updater = baseProps.onCollapsedPopoverChange.mock.calls[0][0];
    expect(typeof updater).toBe('function');
    expect(updater('AI 助手')).toBe(null); // 已打开 → 关闭
    expect(updater(null)).toBe('AI 助手'); // 未打开 → 打开
  });

  it('collapsed 态 Popover 打开时渲染权限过滤后的浮动子菜单', () => {
    renderSubMenu({ isCollapsed: true, collapsedPopoverOpen: 'AI 助手', hasPermission: (perm) => perm === null });
    // 浮动子菜单中的链接（权限过滤 admin 项）
    expect(screen.getByText('智能助手')).toBeInTheDocument();
    expect(screen.queryByText('知识库管理')).not.toBeInTheDocument(); // admin 被过滤
    expect(screen.getByText('通知中心')).toBeInTheDocument();
  });

  it('expanded 态点击 header 触发 onToggleSubMenu', () => {
    renderSubMenu();
    // expanded 态 header 唯一带 aria-expanded=true（子项 Link 无此属性）
    fireEvent.click(screen.getByRole('menuitem', { expanded: true }));
    expect(baseProps.onToggleSubMenu).toHaveBeenCalledWith('AI 助手');
  });
});
