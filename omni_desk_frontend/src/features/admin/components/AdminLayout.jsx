import { useState, useMemo } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../auth/context/AuthContext';
import './AdminLayout.css';
import {
  UserOutlined,
  FileWordOutlined,
  CalendarOutlined,
  SettingOutlined,
  LeftOutlined,
  HomeOutlined,
  LogoutOutlined,
  AppstoreOutlined,
  ExperimentOutlined,
  BellOutlined,
  ReadOutlined,
  ProjectOutlined,
  FileTextOutlined,
  DownOutlined,
  RightOutlined,
} from '@ant-design/icons';

const allAdminMenuItems = [
  { to: "/control-panel/personnel", icon: UserOutlined, text: "人员管理", permission: "personnel.view_personnel" },
  { to: "/control-panel/documents", icon: FileWordOutlined, text: "文档管理", permission: "documents.view_documenttemplate" },
  { to: "/control-panel/schedule", icon: CalendarOutlined, text: "排班管理", permission: "events.view_schedule" },
  { to: "/control-panel/users", icon: UserOutlined, text: "用户管理", permission: "users.view_customuser" },
  { to: "/control-panel/sensors", icon: ExperimentOutlined, text: "传感器管理", permission: "sensors.view_sensor" },
  { to: "/control-panel/ebooks", icon: ReadOutlined, text: "电子书管理", permission: "documents.view_ebook" },
  { to: "/control-panel/announcements/manage", icon: BellOutlined, text: "公告管理", permission: "events.view_announcement" },
  { to: "/control-panel/dify-apps", icon: AppstoreOutlined, text: "Dify 应用管理", permission: "dify_apps.view_difyapp" },
  { to: "/control-panel/schedule/settings", icon: SettingOutlined, text: "排班设置", permission: "events.view_personnelsequence" },
  { to: "/control-panel/meeting-rooms", icon: SettingOutlined, text: "会议室管理", permission: "meeting_rooms.view_meetingroom" },
  { to: "/control-panel/schedule/holiday", icon: CalendarOutlined, text: "节假日管理", permission: "events.view_holiday" },
  { to: "/control-panel/projects", icon: ProjectOutlined, text: "项目管理", permission: "admin" },
  { to: "/control-panel/smart-assistant/audit", icon: FileTextOutlined, text: "Agent 审计", permission: "admin" },
  { to: "/docs/cdepsio6", icon: FileTextOutlined, text: "文档", permission: "admin" },
  { to: "/library", icon: ReadOutlined, text: "书库", permission: "admin" }
];

const AdminLayout = () => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [openSubmenu, setOpenSubmenu] = useState(null);
  const { user, isAuthenticated, logout, hasPermission } = useAuth();
  const location = useLocation();

  const menuItems = useMemo(() => {
    if (isAuthenticated && user) {
      return allAdminMenuItems.filter(item =>
        item.permission ? hasPermission(item.permission) : true
      );
    }
    return [];
  }, [isAuthenticated, user, hasPermission]);


  return (
    <div className="admin-layout">
      <div className={`admin-sidebar ${isCollapsed ? 'collapsed' : ''}`}>
        <div className="admin-sidebar-header">
          <h2>管理面板</h2>
          <button
            className="collapse-toggle"
            onClick={() => setIsCollapsed(!isCollapsed)}
          >
            <LeftOutlined className={`collapse-icon ${isCollapsed ? 'rotate' : ''}`} />
          </button>
        </div>
        <nav className="admin-sidebar-menu">
          <ul>
            {(menuItems || []).map((item, index) => {
              const Icon = item.icon;
              return (
                <li key={index}>
                  {item.children ? (
                    <div
                      className={`menu-item ${location.pathname.startsWith(item.to) ? 'active' : ''} ${openSubmenu === item.text ? 'open' : ''}`}
                      onClick={() => setOpenSubmenu(openSubmenu === item.text ? null : item.text)}
                      title={isCollapsed ? item.text : ''}
                    >
                      <div className="menu-item-content">
                        <Icon className="icon" />
                        {!isCollapsed && <span>{item.text}</span>}
                        {!isCollapsed && (
                          <span className="submenu-caret">
                            {openSubmenu === item.text ? <DownOutlined /> : <RightOutlined />}
                          </span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <Link
                      to={item.to}
                      className={`menu-item ${location.pathname === item.to ? 'active' : ''}`}
                      title={isCollapsed ? item.text : ''}
                    >
                      <div className="menu-item-content">
                        <Icon className="icon" />
                        {!isCollapsed && <span>{item.text}</span>}
                      </div>
                    </Link>
                  )}
                  {item.children && openSubmenu === item.text && (
                    <ul className="submenu">
                      {item.children.map((subItem, subIndex) => (
                        <li key={subIndex}>
                          <Link
                            to={subItem.to}
                            className={`submenu-item ${location.pathname === subItem.to ? 'active' : ''}`}
                            title={isCollapsed ? subItem.text : ''}
                          >
                            {!isCollapsed && <span>{subItem.text}</span>}
                          </Link>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
            <li>
              <Link to="/" className="menu-item">
                <HomeOutlined className="icon" />
                {!isCollapsed && <span>返回主页</span>}
              </Link>
            </li>
            <li>
              <button
                className="menu-item"
                onClick={logout}
              >
                <LogoutOutlined className="icon" />
                {!isCollapsed && <span>退出登录</span>}
              </button>
            </li>
          </ul>
        </nav>
      </div>
      <div className="admin-content">
        <Outlet />
      </div>
    </div>
  );
};

export default AdminLayout;