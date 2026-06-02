import { createMainMenuItems, enrichMenuItems } from './menuConfig';

describe('menuConfig additional', () => {
  it('should export createMainMenuItems function', () => {
    expect(typeof createMainMenuItems).toBe('function');
  });

  it('should export enrichMenuItems function', () => {
    expect(typeof enrichMenuItems).toBe('function');
  });

  it('createMainMenuItems should return array', () => {
    const items = createMainMenuItems({ logout: () => {}, unreadNotificationCount: 0 });
    expect(Array.isArray(items)).toBe(true);
    expect(items.length).toBeGreaterThan(0);
  });
});
