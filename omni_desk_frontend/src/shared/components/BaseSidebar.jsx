import { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { Link, useLocation } from 'react-router-dom';
import {
  DownOutlined,
  LeftOutlined,
} from '@ant-design/icons';
import { Tooltip, Popover } from 'antd';

const DEFAULT_STORAGE_KEY = 'sidebar_collapsed';

/**
 * Reusable sidebar component shared by main app and admin panel.
 * Supports collapse, submenus, permission filtering, and collapsed popover menus.
 */
const BaseSidebar = ({
  brandName = 'OmniDesk',
  brandSubtitle,
  menuItems = [],
  extraHeaderContent,
  isCollapsed: controlledCollapsed,
  defaultCollapsed = false,
  storageKey = DEFAULT_STORAGE_KEY,
  onCollapseChange,
  iconRenderer,
  collapsedIconSize = '1.4rem',
  mobileMenuOpen = false,
  className = '',
}) => {
  const isControlled = controlledCollapsed !== undefined;
  const [internalCollapsed, setInternalCollapsed] = useState(() => {
    try {
      return localStorage.getItem(storageKey) === 'true';
    } catch {
      return defaultCollapsed;
    }
  });
  const isCollapsed = isControlled ? controlledCollapsed : internalCollapsed;

  const [expandedSubMenu, setExpandedSubMenu] = useState({});
  const [collapsedPopoverOpen, setCollapsedPopoverOpen] = useState(null);
  const location = useLocation();

  const toggleSubMenu = useCallback((text) => {
    setExpandedSubMenu(prev => ({ ...prev, [text]: !prev[text] }));
  }, []);

  const setCollapsed = useCallback((value) => {
    const next = typeof value === 'function' ? value(isCollapsed) : value;
    if (!isControlled) setInternalCollapsed(next);
    onCollapseChange?.(next);
    try {
      localStorage.setItem(storageKey, String(next));
    } catch {
      // ignore
    }
  }, [isCollapsed, isControlled, onCollapseChange, storageKey]);

  // Prevent body scroll when mobile menu is open
  useEffect(() => {
    document.body.style.overflow = mobileMenuOpen ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [mobileMenuOpen]);

  const handleToggle = useCallback((itemText, collapsed) => {
    if (collapsed) {
      setCollapsedPopoverOpen(prev => prev === itemText ? null : itemText);
    } else {
      toggleSubMenu(itemText);
    }
  }, [toggleSubMenu]);

  const renderMenuItems = useCallback((items) => {
    return items.map((item, index) => {
      if (item.type === 'divider') {
        return <li key={index} className="menu-divider" />;
      }

      if (item.type === 'button') {
        const Icon = item.icon;
        const buttonContent = (
          <div className="menu-item-content">
            {iconRenderer ? iconRenderer(item.icon, isCollapsed) : <Icon className="icon" style={{ fontSize: collapsedIconSize }} />}
            {!isCollapsed && <span>{item.text}</span>}
          </div>
        );
        return (
          <li key={index} role="none">
            {isCollapsed ? (
              <Tooltip title={item.text} placement="right">
                <button className="menu-item" role="menuitem" onClick={item.action}>
                  {buttonContent}
                </button>
              </Tooltip>
            ) : (
              <button className="menu-item" role="menuitem" onClick={item.action}>
                {buttonContent}
              </button>
            )}
          </li>
        );
      }

      if (item.type === 'submenu') {
        const Icon = item.icon;
        const isSubMenuActive = item.subItems?.some(sub => location.pathname === sub.to);
        const isSubMenuExpanded = expandedSubMenu[item.text] || false;
        const filteredSubItems = (item.subItems || []).filter(subItem => !subItem.permission || item._hasPermission?.(subItem.permission));

        const subMenuHeader = (
          <div
            className={`menu-item ${isSubMenuActive ? 'active' : ''}`}
            role="menuitem"
            aria-expanded={isCollapsed ? undefined : isSubMenuExpanded}
            aria-haspopup={isCollapsed ? 'true' : undefined}
            tabIndex={0}
            onClick={() => handleToggle(item.text, isCollapsed)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleToggle(item.text, isCollapsed);
              }
            }}
          >
            <div className="menu-item-content">
              {iconRenderer ? iconRenderer(item.icon, isCollapsed) : <Icon className="icon" style={{ fontSize: collapsedIconSize }} />}
              {!isCollapsed && (
                <>
                  <span>{item.text}</span>
                  <DownOutlined className={`submenu-arrow ${isSubMenuExpanded ? 'expanded' : ''}`} />
                </>
              )}
            </div>
          </div>
        );

        if (isCollapsed && filteredSubItems.length > 0) {
          return (
            <li key={index} role="none">
              <Tooltip title={item.text} placement="right">
                {subMenuHeader}
              </Tooltip>
              <Popover
                open={collapsedPopoverOpen === item.text}
                placement="rightTop"
                trigger="click"
                title={null}
                content={
                  <ul className="submenu popover-submenu" role="menu">
                    {filteredSubItems.map((subItem, subIndex) => {
                      const SubIcon = subItem.icon;
                      return (
                        <li key={subIndex} role="none">
                          <Link
                            to={subItem.to}
                            className={`menu-item ${location.pathname === subItem.to ? 'active' : ''}`}
                            onClick={() => setCollapsedPopoverOpen(null)}
                          >
                            <div className="menu-item-content">
                              {SubIcon && (iconRenderer ? iconRenderer(SubIcon, false) : <SubIcon className="icon" />)}
                              <span>{subItem.text}</span>
                              {subItem.badgeCount !== undefined && subItem.badgeCount > 0 && item._renderBadge?.(subItem.badgeCount)}
                            </div>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                }
              />
            </li>
          );
        }

        return (
          <li key={index} role="none">
            {subMenuHeader}
            <ul className={`submenu ${isSubMenuExpanded ? 'expanded' : ''}`} role="menu">
              {filteredSubItems.map((subItem, subIndex) => {
                const SubIcon = subItem.icon;
                return (
                  <li key={subIndex} role="none">
                    <Link
                      to={subItem.to}
                      className={`menu-item ${location.pathname === subItem.to ? 'active' : ''}`}
                      role="menuitem"
                      aria-current={location.pathname === subItem.to ? 'page' : undefined}
                    >
                      <div className="menu-item-content">
                        {SubIcon && (iconRenderer ? iconRenderer(SubIcon, false) : <SubIcon className="icon" />)}
                        <span>{subItem.text}</span>
                        {subItem.badgeCount !== undefined && subItem.badgeCount > 0 && item._renderBadge?.(subItem.badgeCount)}
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </li>
        );
      }

      // Default: link item
      const Icon = item.icon;
      const linkContent = (
        <div className="menu-item-content">
          {iconRenderer ? iconRenderer(item.icon, isCollapsed) : <Icon className="icon" style={{ fontSize: collapsedIconSize }} />}
          {!isCollapsed && <span>{item.text}</span>}
        </div>
      );
      const link = (
        <Link
          to={item.to}
          className={`menu-item ${location.pathname === item.to ? 'active' : ''}`}
          role="menuitem"
          aria-current={location.pathname === item.to ? 'page' : undefined}
        >
          {linkContent}
        </Link>
      );

      return (
        <li key={index} role="none">
          {isCollapsed && item.tooltip !== false ? (
            <Tooltip title={item.text} placement="right">
              {link}
            </Tooltip>
          ) : (
            link
          )}
        </li>
      );
    });
  }, [isCollapsed, location.pathname, expandedSubMenu, collapsedPopoverOpen, iconRenderer, collapsedIconSize, handleToggle]);

  return (
    <div className={`sidebar ${className} ${mobileMenuOpen ? 'active' : ''} ${isCollapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <div className="sidebar-brand">
          {!isCollapsed && (
            <>
              <div className="brand-name">{brandName}</div>
              {brandSubtitle && <div className="brand-subtitle">{brandSubtitle}</div>}
            </>
          )}
        </div>
        {extraHeaderContent && !isCollapsed && extraHeaderContent}
        {!mobileMenuOpen && (
          <button
            className="collapse-toggle"
            onClick={() => setCollapsed(!isCollapsed)}
            aria-label={isCollapsed ? '展开侧边栏' : '收起侧边栏'}
          >
            <LeftOutlined className={`collapse-icon ${isCollapsed ? 'rotate' : ''}`} />
          </button>
        )}
      </div>
      <nav className="sidebar-menu" role="menu" aria-label="主导航菜单">
        <ul>
          {renderMenuItems(menuItems)}
        </ul>
      </nav>
    </div>
  );
};

BaseSidebar.propTypes = {
  brandName: PropTypes.string,
  brandSubtitle: PropTypes.string,
  menuItems: PropTypes.array.isRequired,
  extraHeaderContent: PropTypes.node,
  isCollapsed: PropTypes.bool,
  defaultCollapsed: PropTypes.bool,
  storageKey: PropTypes.string,
  onCollapseChange: PropTypes.func,
  iconRenderer: PropTypes.func,
  collapsedIconSize: PropTypes.string,
  mobileMenuOpen: PropTypes.bool,
  className: PropTypes.string,
};

export default BaseSidebar;
