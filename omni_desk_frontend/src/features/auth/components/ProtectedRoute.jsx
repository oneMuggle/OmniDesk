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

  // 严格模式:显式传入 permissions 时,用户需满足 permissions ∪ {pagePath}
  // 中任意一项(pagePath 用于兼容用户组的页面授权 GroupPagePermission →
  // PageRoute.path),否则跳转 /unauthorized。管理中心路由全部走这里,
  // 权限来源见 features/admin/config/adminRoutePermissions.js。
  if (permissions !== null && permissions !== undefined) {
    const required = [
      ...(Array.isArray(permissions) ? permissions : [permissions]),
      ...(pagePath ? [pagePath] : []),
    ];
    if (!hasPermission(required)) {
      return <Navigate to="/unauthorized" replace />;
    }
    return children;
  }

  // 未传 permissions(主应用页面,仅 pagePath 或都不传):保持历史行为。
  // 主应用路由普遍以 <ProtectedRoute pagePath="/memos"> 形式声明,而多数用户组
  // 并未配置对应的 PageRoute 授权;若严格校验会把普通用户挡在日常页面之外。
  // 因此 URL 形态的 pagePath 在校验失败时仍放行已登录用户(页面数据由后端 API
  // 鉴权)。收紧主应用页面权限需先核对生产环境授权数据,另行评估。
  const looksLikeUrl = typeof pagePath === 'string' && pagePath.startsWith('/');
  if (!hasPermission(pagePath)) {
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
