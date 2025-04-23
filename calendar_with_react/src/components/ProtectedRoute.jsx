import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { checkPermission } from '../config/permissionConfig';

const ProtectedRoute = ({ 
  children, 
  allowGuest = false, 
  requireAuth = false,
  requiredPermissions = []
}) => {
  const { isAuthenticated, isInitializing, isGuest, hasPermission } = useAuth();

  if (isInitializing) {
    return <div>Loading...</div>;
  }

  if (requireAuth && !isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (allowGuest && (isAuthenticated || isGuest)) {
    return React.cloneElement(children, { isGuest });
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // 使用AuthContext提供的hasPermission方法
  const hasAllPermissions = requiredPermissions.every(perm => hasPermission(perm));
  if (!hasAllPermissions) {
    const missingPermissions = requiredPermissions.filter(perm => !hasPermission(perm));
    console.warn('权限检查失败', {
      requestedPermissions: requiredPermissions,
      missingPermissions
    });
    return (
      <Navigate 
        to="/unauthorized" 
        replace 
        state={{ 
          missingPermissions,
          message: `缺少权限: ${missingPermissions.join(', ')}`
        }} 
      />
    );
  }

  return children;
};

export default ProtectedRoute;
