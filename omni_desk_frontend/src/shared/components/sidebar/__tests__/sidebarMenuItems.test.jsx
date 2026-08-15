import { createMenuItems, createUserDropdownItems } from '../sidebarMenuItems';

describe('createMenuItems', () => {
  const logout = jest.fn();
  const unreadNotificationCount = 3;

  it('生成主菜单数组并注入退出登录 action', () => {
    const items = createMenuItems({ logout, unreadNotificationCount });
    const logoutItem = items.find(item => item.type === 'button');
    expect(logoutItem).toMatchObject({ icon: expect.anything(), text: '退出登录' });
    expect(logoutItem.action).toBe(logout);
  });

  it('通知中心 badgeCount 引用 unreadNotificationCount', () => {
    const items = createMenuItems({ logout, unreadNotificationCount });
    const projectMenu = items.find(item => item.type === 'submenu' && item.text === '项目管理');
    const notificationItem = projectMenu.subItems.find(sub => sub.text === '通知中心');
    expect(notificationItem.badgeCount).toBe(3);
  });

  it('日历子菜单含 3 项', () => {
    const items = createMenuItems({ logout, unreadNotificationCount });
    const calendarMenu = items.find(item => item.type === 'submenu' && item.text === '日历');
    expect(calendarMenu.subItems.map(sub => sub.text)).toEqual(['试验日程', '排班日程', '会议室预约']);
  });

  it('AI 助手子菜单为当前 7 项', () => {
    const items = createMenuItems({ logout, unreadNotificationCount });
    const aiMenu = items.find(item => item.type === 'submenu' && item.text === 'AI 助手');
    expect(aiMenu.subItems.map(sub => sub.text)).toEqual([
      '智能助手', '多Agent任务', '知识库管理', 'Ragflow 聊天', 'Dify 应用', 'Office 助手', '文件分析',
    ]);
  });

  it('管理中心权限为 admin+manager', () => {
    const items = createMenuItems({ logout, unreadNotificationCount });
    const controlPanel = items.find(item => item.text === '管理中心');
    expect(controlPanel.permission).toEqual(['admin', 'manager']);
  });

  it('项目管理子菜单仅 admin 可见', () => {
    const items = createMenuItems({ logout, unreadNotificationCount });
    const projectMenu = items.find(item => item.type === 'submenu' && item.text === '项目管理');
    expect(projectMenu.permission).toBe('admin');
  });
});

describe('createUserDropdownItems', () => {
  const navigate = jest.fn();
  const logout = jest.fn();

  it('生成 profile/settings/divider/logout 四项', () => {
    const items = createUserDropdownItems({ navigate, logout });
    expect(items.map(item => item.key || item.type)).toEqual(['profile', 'settings', 'divider', 'logout']);
  });

  it('退出登录项带 danger 且点击时 logout + 跳转', () => {
    const items = createUserDropdownItems({ navigate, logout });
    const logoutItem = items.find(item => item.key === 'logout');
    expect(logoutItem.danger).toBe(true);
    logoutItem.onClick();
    expect(logout).toHaveBeenCalled();
    expect(navigate).toHaveBeenCalledWith('/login');
  });

  it('个人资料/设置项导航到对应路由', () => {
    const items = createUserDropdownItems({ navigate, logout });
    items.find(item => item.key === 'profile').onClick();
    expect(navigate).toHaveBeenCalledWith('/profile');
    items.find(item => item.key === 'settings').onClick();
    expect(navigate).toHaveBeenCalledWith('/control-panel');
  });
});
