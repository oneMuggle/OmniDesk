import { Navigate } from 'react-router-dom';
import { useAuth } from '../../auth/context/AuthContext';
import { requiredForAdminRoute } from '../config/adminRoutePermissions';
import { AI_MANAGEMENT_BASE, AI_MANAGEMENT_TABS } from '../config/aiManagementTabs';

/** /control-panel/ai 首页:跳到第一个有权限的标签。 */
const AiManagementIndex = () => {
  const { hasPermission } = useAuth();
  const first = AI_MANAGEMENT_TABS.find((tab) => hasPermission(requiredForAdminRoute(tab.route)));
  return <Navigate to={first ? `${AI_MANAGEMENT_BASE}/${first.key}` : '/unauthorized'} replace />;
};

export default AiManagementIndex;
