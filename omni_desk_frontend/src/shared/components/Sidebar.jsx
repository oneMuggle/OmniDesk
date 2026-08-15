import { useState, useEffect, useMemo, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../features/auth/context/AuthContext';
import { MenuOutlined } from '@ant-design/icons';
import notificationApi from '../../features/notifications/api/notificationApi';
import { logger } from '../utils/logger';
import SidebarHeader from './sidebar/SidebarHeader';
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
  const [unreadNotificationCount, setUnreadNotificationCount] = useState(0);

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

  // Notification polling — pause when sidebar is collapsed
  useEffect(() => {
    const fetchUnreadCount = async () => {
      try {
        const response = await notificationApi.getUnreadCount();
        setUnreadNotificationCount(response.data.unread_count);
      } catch (error) {
        logger.error('Error fetching unread notification count:', error);
      }
    };

    if (isAuthenticated && !isCollapsed) {
      fetchUnreadCount();
      const interval = setInterval(fetchUnreadCount, 60000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated, isCollapsed]);

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
        <nav className="sidebar-menu" role="menu" aria-label="主导航菜单">
          <ul>
            {menuItems.filter(item => hasPermission(item.permission)).map(renderMenuItem)}
          </ul>
        </nav>
      </div>
      {!isMobileMenuOpen && (
        <button className="mobile-menu-toggle" onClick={toggleMobileMenu}>
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
