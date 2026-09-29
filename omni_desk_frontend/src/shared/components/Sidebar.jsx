import { useState, useEffect, useMemo, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useLocation, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '../../features/auth/context/AuthContext';
import { MenuOutlined, SearchOutlined } from '@ant-design/icons';
import notificationApi from '../../features/notifications/api/notificationApi';
import { logger } from '../utils/logger';
import SidebarHeader from './sidebar/SidebarHeader';
import UnifiedSearchBar from '../../features/search-federation/components/UnifiedSearchBar';
import SidebarButtonItem from './sidebar/SidebarButtonItem';
import SidebarLinkItem from './sidebar/SidebarLinkItem';
import SidebarSubMenu from './sidebar/SidebarSubMenu';
import { createMenuItems, createUserDropdownItems } from './sidebar/sidebarMenuItems';

const STORAGE_KEY = 'sidebar_collapsed';

const Sidebar = ({ isMobileMenuOpen = false, toggleMobileMenu = () => {} }) => {
  const [isCollapsed, setIsCollapsed] = useState(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  });
  const [expandedSubMenu, setExpandedSubMenu] = useState({ '日历': true });
  const [collapsedPopoverOpen, setCollapsedPopoverOpen] = useState(null);
  const { isAuthenticated, user, logout, hasPermission, isGuest } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // R4-B1: 未读数与 NotificationBell 共享同一 RQ query(['unreadCount']),
  // 删除 Sidebar 自己的 setInterval 手写轮询(双轨轮询 → 单轨)。
  // refetchInterval 由 NotificationBell(5s)驱动,此处只读共享缓存,不再重复发请求。
  const { data: unreadData } = useQuery({
    queryKey: ['unreadCount'],
    queryFn: () => notificationApi.getUnreadCount().then((r) => r.data),
    enabled: isAuthenticated,
    refetchOnWindowFocus: false,
  });
  const unreadNotificationCount = unreadData?.unread_count || 0;

  // Persist collapse state
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, String(isCollapsed));
    } catch (e) {
      logger.warn('Failed to save sidebar state:', e);
    }
  }, [isCollapsed]);

  // Prevent body scroll when mobile menu is open
  useEffect(() => {
    document.body.style.overflow = isMobileMenuOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [isMobileMenuOpen]);

  // T3: ESC 关闭移动端菜单 (a11y, 与 App.jsx 的全局监听互为冗余保障)
  useEffect(() => {
    if (!isMobileMenuOpen) return undefined;
    const onKeyDown = (e) => {
      if (e.key === 'Escape') toggleMobileMenu();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [isMobileMenuOpen, toggleMobileMenu]);

  const menuItems = useMemo(
    () => createMenuItems({ logout, unreadNotificationCount }),
    [logout, unreadNotificationCount]
  );
  const userDropdownItems = useMemo(
    () => createUserDropdownItems({ navigate, logout }),
    [navigate, logout]
  );

  const toggleSubMenu = useCallback((text) => {
    setExpandedSubMenu(prev => ({ ...prev, [text]: !prev[text] }));
  }, []);

  const renderMenuItem = (item, index) => {
    if (item.type === 'button') {
      return (
        <SidebarButtonItem
          key={index}
          item={item}
          isCollapsed={isCollapsed}
          isMobileMenuOpen={isMobileMenuOpen}
          onCloseMobile={toggleMobileMenu}
        />
      );
    }
    if (item.type === 'submenu') {
      return (
        <SidebarSubMenu
          key={index}
          item={item}
          isCollapsed={isCollapsed}
          isMobileMenuOpen={isMobileMenuOpen}
          location={location}
          hasPermission={hasPermission}
          expandedSubMenu={expandedSubMenu}
          collapsedPopoverOpen={collapsedPopoverOpen}
          onToggleSubMenu={toggleSubMenu}
          onCollapsedPopoverChange={setCollapsedPopoverOpen}
          onCloseMobile={toggleMobileMenu}
        />
      );
    }
    return (
      <SidebarLinkItem
        key={index}
        item={item}
        isCollapsed={isCollapsed}
        isMobileMenuOpen={isMobileMenuOpen}
        location={location}
        onCloseMobile={toggleMobileMenu}
      />
    );
  };

  return (
    <>
      <div className={`sidebar ${isMobileMenuOpen ? 'active' : ''} ${isCollapsed ? 'collapsed' : ''}`}>
        <SidebarHeader
          isAuthenticated={isAuthenticated}
          user={user}
          isGuest={isGuest}
          isCollapsed={isCollapsed}
          isMobileMenuOpen={isMobileMenuOpen}
          userDropdownItems={userDropdownItems}
          onToggleCollapsed={() => setIsCollapsed(!isCollapsed)}
          onCloseMobile={toggleMobileMenu}
          onNavigate={navigate}
        />
        {isAuthenticated && !isGuest && (
          <div className="sidebar-search">
            {!isCollapsed ? (
              <UnifiedSearchBar placeholder="搜索项目、备忘录、人员..." style={{ width: '100%' }} />
            ) : (
              <button
                className="sidebar-search-collapsed-btn"
                aria-label="搜索"
                title="展开搜索"
                onClick={() => setIsCollapsed(false)}
              >
                <SearchOutlined />
              </button>
            )}
          </div>
        )}
        <nav className="sidebar-menu" role="navigation" aria-label="主导航菜单">
          <ul role="list">
            {menuItems.filter(item => hasPermission(item.permission)).map(renderMenuItem)}
          </ul>
        </nav>
      </div>
      {!isMobileMenuOpen && (
        <button
          className="mobile-menu-toggle"
          onClick={toggleMobileMenu}
          aria-label="打开导航菜单"
          aria-expanded={isMobileMenuOpen}
        >
          <MenuOutlined />
        </button>
      )}
    </>
  );
};

Sidebar.propTypes = {
  isMobileMenuOpen: PropTypes.bool,
  toggleMobileMenu: PropTypes.func,
};

export default Sidebar;
