import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = ({ children, roles, pagePath }) => { // 添加 pagePath 属性
  const { user, isAuthenticated, isInitializing, isPageVisible } = useAuth(); // 导入 isPageVisible

  if (isInitializing) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (roles && !roles.includes(user?.role)) {
    return <Navigate to="/unauthorized" replace />;
  }

  // 根据 pagePath 判断页面可见性
  if (pagePath && !isPageVisible(pagePath)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};

export default ProtectedRoute;
