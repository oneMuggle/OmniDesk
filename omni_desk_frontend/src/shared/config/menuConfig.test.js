import { createMainMenuItems, enrichMenuItems } from './menuConfig';

jest.mock('antd', () => ({
  Badge: function MockBadge({ count }) {
    return `Badge(${count})`;
  },
}));

describe('menuConfig', () => {
  describe('createMainMenuItems', () => {
    it('should create menu items with logout function', () => {
      const mockLogout = jest.fn();
      const items = createMainMenuItems({ logout: mockLogout, unreadNotificationCount: 0 });
      expect(items.length).toBeGreaterThan(0);
      const logoutItem = items.find(item => item.text === '退出登录');
      expect(logoutItem).toBeDefined();
      expect(logoutItem.action).toBe(mockLogout);
    });

    it('should include notification badge count', () => {
      const items = createMainMenuItems({ logout: jest.fn(), unreadNotificationCount: 5 });
      const projectSubmenu = items.find(item => item.text === '项目管理');
      expect(projectSubmenu).toBeDefined();
      const notifItem = projectSubmenu.subItems.find(item => item.text === '通知中心');
      expect(notifItem.badgeCount).toBe(5);
    });

    it('should include submenu items for calendar', () => {
      const items = createMainMenuItems({ logout: jest.fn(), unreadNotificationCount: 0 });
      const calendarSubmenu = items.find(item => item.text === '日历');
      expect(calendarSubmenu).toBeDefined();
      expect(calendarSubmenu.type).toBe('submenu');
      expect(calendarSubmenu.subItems.length).toBe(3);
    });

    it('should include submenu items for AI assistant', () => {
      const items = createMainMenuItems({ logout: jest.fn(), unreadNotificationCount: 0 });
      const aiSubmenu = items.find(item => item.text === 'AI 助手');
      expect(aiSubmenu).toBeDefined();
      expect(aiSubmenu.subItems.length).toBe(5);
    });

    it('should have admin permission on management center', () => {
      const items = createMainMenuItems({ logout: jest.fn(), unreadNotificationCount: 0 });
      const adminItem = items.find(item => item.text === '管理中心');
      expect(adminItem.permission).toEqual(['admin', 'manager']);
    });
  });

  describe('enrichMenuItems', () => {
    it('should enrich submenu items with hasPermission', () => {
      const mockHasPermission = jest.fn();
      const items = createMainMenuItems({ logout: jest.fn(), unreadNotificationCount: 0 });
      const enriched = enrichMenuItems(items, mockHasPermission);
      const calendarSubmenu = enriched.find(item => item.type === 'submenu');
      expect(calendarSubmenu._hasPermission).toBe(mockHasPermission);
      expect(calendarSubmenu.subItems).toBeDefined();
    });

    it('should not modify non-submenu items', () => {
      const items = createMainMenuItems({ logout: jest.fn(), unreadNotificationCount: 0 });
      const homeItem = items.find(item => item.text === '首页');
      const enriched = enrichMenuItems([homeItem], jest.fn());
      expect(enriched[0]._hasPermission).toBeUndefined();
    });
  });
});
