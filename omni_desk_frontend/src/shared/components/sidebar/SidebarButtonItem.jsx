import PropTypes from 'prop-types';
import { Tooltip } from 'antd';

/**
 * 按钮型菜单项（退出登录）渲染 + collapsed Tooltip。
 * 逐字搬自原 Sidebar.jsx renderMenuItem 的 button 支（L139-171），行为零变化。
 */
const SidebarButtonItem = ({ item, isCollapsed, isMobileMenuOpen, onCloseMobile }) => {
  const Icon = item.icon;
  const buttonContent = (
    <div className="menu-item-content">
      <Icon className="icon" />
      {!isCollapsed && <span>{item.text}</span>}
    </div>
  );
  const button = (
    <button
      className="menu-item"
      role="menuitem"
      onClick={() => {
        item.action();
        if (isMobileMenuOpen) onCloseMobile();
      }}
    >
      {buttonContent}
    </button>
  );

  return (
    <li role="none">
      {isCollapsed ? (
        <Tooltip title={item.text} placement="right">
          {button}
        </Tooltip>
      ) : (
        button
      )}
    </li>
  );
};

SidebarButtonItem.propTypes = {
  item: PropTypes.shape({
    icon: PropTypes.elementType.isRequired,
    text: PropTypes.string.isRequired,
    action: PropTypes.func.isRequired,
    permission: PropTypes.oneOfType([PropTypes.string, PropTypes.array]),
  }).isRequired,
  isCollapsed: PropTypes.bool,
  isMobileMenuOpen: PropTypes.bool,
  onCloseMobile: PropTypes.func.isRequired,
};

export default SidebarButtonItem;
