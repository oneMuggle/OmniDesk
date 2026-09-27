import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Tabs, Typography } from 'antd';
import { useAuth } from '../../auth/context/AuthContext';
import { requiredForAdminRoute } from '../config/adminRoutePermissions';
import { AI_MANAGEMENT_BASE, AI_MANAGEMENT_TABS } from '../config/aiManagementTabs';

/**
 * 控制台「AI 管理」(S2-2):使用统计 / Agent 审计 / AI 应用配置三个标签。
 * 每个标签按各自权限显示;子路由另有独立的 ProtectedRoute 守卫。
 */
const AiManagementLayout = () => {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { hasPermission } = useAuth();
  const tabs = AI_MANAGEMENT_TABS.filter((tab) => hasPermission(requiredForAdminRoute(tab.route)));
  const active = tabs.find((tab) => pathname.startsWith(`${AI_MANAGEMENT_BASE}/${tab.key}`));

  return (
    <div className="ai-management-layout" data-testid="ai-management-layout">
      <Typography.Title level={4} style={{ margin: '0 0 8px' }}>
        AI 管理
      </Typography.Title>
      <Tabs
        activeKey={active?.key}
        onChange={(key) => navigate(`${AI_MANAGEMENT_BASE}/${key}`)}
        items={tabs.map(({ key, label }) => ({ key, label }))}
      />
      <Outlet />
    </div>
  );
};

export default AiManagementLayout;
