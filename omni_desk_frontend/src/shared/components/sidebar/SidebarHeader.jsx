import PropTypes from 'prop-types';
import { Avatar, Dropdown } from 'antd';
import { DownOutlined, LeftOutlined, UserOutlined } from '@ant-design/icons';
import NotificationBell from '../../../features/notifications/components/NotificationBell';
import ThemeSelector from '../ThemeSelector';
import DemoToggle from '../DemoToggle';

/**
 * 侧边栏 header：brand + 用户下拉 + 通知铃 + 游客区 + 主题/Demo + 折叠/关闭按钮。
 * 逐字搬自原 Sidebar.jsx 主 JSX 的 header 区块（L365-425），行为零变化。
 */
const SidebarHeader = ({
  isAuthenticated,
  user,
  isGuest,
  isCollapsed,
  isMobileMenuOpen,
  userDropdownItems,
  onToggleCollapsed,
  onCloseMobile,
  onNavigate,
}) => (
  <div className="sidebar-header">
    <div className="sidebar-brand">
      {!isCollapsed && (
        <>
          <div className="brand-name">OmniDesk</div>
          <div className="brand-subtitle">智能办公系统</div>
        </>
      )}
    </div>

    {isAuthenticated && !isCollapsed && (
      <Dropdown menu={{ items: userDropdownItems }} placement="bottomRight" trigger={['click']}>
        <div className="user-dropdown-trigger">
          <Avatar size="small" icon={<UserOutlined />} className="user-avatar" />
          <span className="username">{user?.username || '用户'}</span>
          <DownOutlined className="dropdown-arrow" />
        </div>
      </Dropdown>
    )}

    {isAuthenticated && (
      <div className="sidebar-notification-bell">
        <NotificationBell />
      </div>
    )}

    {isGuest && !isCollapsed && (
      <div className="guest-info">
        <Avatar size="small" icon={<UserOutlined />} className="user-avatar" />
        <span className="guest-label">游客</span>
        <button
          className="guest-login-btn"
          onClick={() => onNavigate('/login')}
        >
          登录/注册
        </button>
      </div>
    )}

    {isAuthenticated && !isCollapsed && (
      <>
        <ThemeSelector />
        <DemoToggle />
      </>
    )}

    {isMobileMenuOpen && (
      <button className="close-menu" onClick={onCloseMobile}>
        &times;
      </button>
    )}
    {!isMobileMenuOpen && (
      <button
        className="collapse-toggle"
        onClick={onToggleCollapsed}
        aria-label={isCollapsed ? '展开侧边栏' : '收起侧边栏'}
      >
        <LeftOutlined className={`collapse-icon ${isCollapsed ? 'rotate' : ''}`} />
      </button>
    )}
  </div>
);

SidebarHeader.propTypes = {
  isAuthenticated: PropTypes.bool,
  user: PropTypes.shape({
    username: PropTypes.string,
  }),
  isGuest: PropTypes.bool,
  isCollapsed: PropTypes.bool,
  isMobileMenuOpen: PropTypes.bool,
  userDropdownItems: PropTypes.arrayOf(PropTypes.shape({
    key: PropTypes.string,
    label: PropTypes.string,
    danger: PropTypes.bool,
    type: PropTypes.oneOf(['divider']),
  })),
  onToggleCollapsed: PropTypes.func.isRequired,
  onCloseMobile: PropTypes.func.isRequired,
  onNavigate: PropTypes.func.isRequired,
};

export default SidebarHeader;
