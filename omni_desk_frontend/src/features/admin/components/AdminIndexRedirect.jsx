import { Navigate } from 'react-router-dom';
import { useAuth } from '../../auth/context/AuthContext';
import {
  ADMIN_INDEX_CANDIDATES,
  requiredForAdminRoute,
} from '../config/adminRoutePermissions';

/**
 * 管理中心首页:跳转到第一个有权限的菜单页,而不是固定跳人员管理
 * (没有人员权限的管理员/经理此前会被直接踢到 /unauthorized)。
 */
const AdminIndexRedirect = () => {
  const { hasPermission } = useAuth();
  const target = ADMIN_INDEX_CANDIDATES.find((routePath) =>
    hasPermission(requiredForAdminRoute(routePath))
  );
  return <Navigate to={target ? `/control-panel/${target}` : '/unauthorized'} replace />;
};

export default AdminIndexRedirect;
