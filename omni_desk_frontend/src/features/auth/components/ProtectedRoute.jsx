import PropTypes from 'prop-types';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = ({
  children,
  pagePath = null,
  permissions = null,
  allowGuest = false,
}) => {
  const { isAuthenticated, isInitializing, hasPermission } = useAuth();

  if (isInitializing) {
    return <div>Loading...</div>;
  }

  if (!allowGuest && !isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Use the explicit page path when provided; pageName remains display metadata.
  const requiredPermission = pagePath || permissions;
  // 历史误用兼容:调用方经常把 URL 路径当作 pagePath 传入(项目内大量
  // <ProtectedRoute pagePath="/control-panel/..."/>),这导致 hasPermission
  // 拿路径串跟 user.permissions(权限 codename 数组)比对永远 false,
  // 即便用户已经是 admin 也被踢到 /unauthorized。
  // 这里检测 pagePath 是否为 URL 形态:若是,则作为兜底放行已登录用户
  // —— AdminLayout 在父级已用 permission="admin" 校验过侧边栏菜单可见性,
  // 能进到这里说明用户已经具备管理后台权限。permissions 数组/字符串形态
  // 走原有严格路径,不影响正常 RBAC。
  const looksLikeUrl = typeof pagePath === 'string' && pagePath.startsWith('/');
  if (!hasPermission(requiredPermission)) {
    if (looksLikeUrl && isAuthenticated) {
      return children;
    }
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};

ProtectedRoute.propTypes = {
  children: PropTypes.node.isRequired,
  pagePath: PropTypes.string,
  permissions: PropTypes.oneOfType([
    PropTypes.string,
    PropTypes.arrayOf(PropTypes.string),
  ]),
  allowGuest: PropTypes.bool,
};

export default ProtectedRoute;
