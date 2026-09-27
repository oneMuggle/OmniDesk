import PropTypes from 'prop-types';
import { Link } from 'react-router-dom';
import { Tooltip } from 'antd';
import { isMenuItemActive } from './sidebarMenuItems';

/**
 * 链接型菜单项渲染 + collapsed Tooltip + active 态。
 * 逐字搬自原 Sidebar.jsx renderMenuItem 的 link 支（L304-333），行为零变化。
 */
const SidebarLinkItem = ({ item, isCollapsed, isMobileMenuOpen, location, onCloseMobile }) => {
  const Icon = item.icon;
  const linkContent = (
    <div className="menu-item-content">
      <Icon className="icon" />
      {!isCollapsed && <span>{item.text}</span>}
    </div>
  );
  const link = (
    <Link
      to={item.to}
      className={`menu-item ${isMenuItemActive(location.pathname, item) ? 'active' : ''}`}
      role="menuitem"
      aria-current={isMenuItemActive(location.pathname, item) ? 'page' : undefined}
      onClick={() => isMobileMenuOpen && onCloseMobile()}
    >
      {linkContent}
    </Link>
  );

  return (
    <li role="none">
      {isCollapsed ? (
        <Tooltip title={item.text} placement="right">
          {link}
        </Tooltip>
      ) : (
        link
      )}
    </li>
  );
};

SidebarLinkItem.propTypes = {
  item: PropTypes.shape({
    to: PropTypes.string.isRequired,
    icon: PropTypes.elementType.isRequired,
    text: PropTypes.string.isRequired,
    permission: PropTypes.oneOfType([PropTypes.string, PropTypes.array]),
    matchPrefix: PropTypes.bool,
  }).isRequired,
  isCollapsed: PropTypes.bool,
  isMobileMenuOpen: PropTypes.bool,
  location: PropTypes.shape({
    pathname: PropTypes.string.isRequired,
  }).isRequired,
  onCloseMobile: PropTypes.func.isRequired,
};

export default SidebarLinkItem;
