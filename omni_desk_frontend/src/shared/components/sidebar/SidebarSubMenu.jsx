import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { Badge, Popover, Tooltip } from 'antd';
import { DownOutlined } from '@ant-design/icons';

/**
 * 子菜单渲染：expanded CSS 动画态 + collapsed Popover 浮动子菜单 + badgeCount。
 * 逐字搬自原 Sidebar.jsx renderMenuItem 的 submenu 支（L173-302），行为零变化。
 */
const SidebarSubMenu = ({
  item,
  isCollapsed,
  isMobileMenuOpen,
  location,
  hasPermission,
  expandedSubMenu,
  collapsedPopoverOpen,
  onToggleSubMenu,
  onCollapsedPopoverChange,
  onCloseMobile,
}) => {
  const Icon = item.icon;
  const isSubMenuActive = item.subItems.some(sub => location.pathname === sub.to);
  const isSubMenuExpanded = expandedSubMenu[item.text] ?? item.subItems.some(sub => location.pathname === sub.to);

  const handleToggle = () => {
    if (isCollapsed) {
      onCollapsedPopoverChange(prev => (prev === item.text ? null : item.text));
    } else {
      onToggleSubMenu(item.text);
    }
  };

  const subMenuHeader = (
    <div
      className={`menu-item ${isSubMenuActive ? 'active' : ''}`}
      role="menuitem"
      aria-expanded={isCollapsed ? undefined : isSubMenuExpanded}
      aria-haspopup={isCollapsed ? 'true' : undefined}
      tabIndex={0}
      onClick={handleToggle}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleToggle();
        }
      }}
    >
      <div className="menu-item-content">
        <Icon className="icon" />
        {!isCollapsed && (
          <>
            <span>{item.text}</span>
            <DownOutlined className={`submenu-arrow ${isSubMenuExpanded ? 'expanded' : ''}`} />
          </>
        )}
      </div>
    </div>
  );

  // Floating submenu for collapsed state
  if (isCollapsed) {
    const filteredSubItems = item.subItems.filter(subItem => hasPermission(subItem.permission));
    if (filteredSubItems.length === 0) {
      return (
        <li role="none">
          <Tooltip title={item.text} placement="right">
            {subMenuHeader}
          </Tooltip>
        </li>
      );
    }
    return (
      <li role="none">
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
                      onClick={() => {
                        onCollapsedPopoverChange(null);
                        if (isMobileMenuOpen) onCloseMobile();
                      }}
                    >
                      <div className="menu-item-content">
                        {SubIcon && <SubIcon className="icon" />}
                        <span>{subItem.text}</span>
                        {subItem.badgeCount !== undefined && subItem.badgeCount > 0 && (
                          <Badge count={subItem.badgeCount} size="small" />
                        )}
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

  // Normal expanded submenu with CSS grid animation
  return (
    <li role="none">
      {subMenuHeader}
      <ul
        className={`submenu ${isSubMenuExpanded ? 'expanded' : ''}`}
        role="menu"
      >
        {item.subItems
          .filter(subItem => hasPermission(subItem.permission))
          .map((subItem, subIndex) => {
            const SubIcon = subItem.icon;
            return (
              <li key={subIndex} role="none">
                <Link
                  to={subItem.to}
                  className={`menu-item ${location.pathname === subItem.to ? 'active' : ''}`}
                  role="menuitem"
                  aria-current={location.pathname === subItem.to ? 'page' : undefined}
                  onClick={() => isMobileMenuOpen && onCloseMobile()}
                >
                  <div className="menu-item-content">
                    {SubIcon && <SubIcon className="icon" />}
                    <span>{subItem.text}</span>
                    {subItem.badgeCount !== undefined && subItem.badgeCount > 0 && (
                      <Badge count={subItem.badgeCount} size="small" />
                    )}
                  </div>
                </Link>
              </li>
            );
          })}
      </ul>
    </li>
  );
};

SidebarSubMenu.propTypes = {
  item: PropTypes.shape({
    text: PropTypes.string.isRequired,
    icon: PropTypes.elementType,
    subItems: PropTypes.arrayOf(PropTypes.shape({
      to: PropTypes.string,
      text: PropTypes.string.isRequired,
      icon: PropTypes.elementType,
      permission: PropTypes.oneOfType([PropTypes.string, PropTypes.array]),
      badgeCount: PropTypes.number,
    })).isRequired,
  }).isRequired,
  isCollapsed: PropTypes.bool,
  isMobileMenuOpen: PropTypes.bool,
  location: PropTypes.shape({
    pathname: PropTypes.string.isRequired,
  }).isRequired,
  hasPermission: PropTypes.func.isRequired,
  expandedSubMenu: PropTypes.object.isRequired,
  collapsedPopoverOpen: PropTypes.string,
  onToggleSubMenu: PropTypes.func.isRequired,
  onCollapsedPopoverChange: PropTypes.func.isRequired,
  onCloseMobile: PropTypes.func.isRequired,
};

export default SidebarSubMenu;
