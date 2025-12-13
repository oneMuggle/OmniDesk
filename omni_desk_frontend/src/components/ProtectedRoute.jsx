import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = ({ children, permissions }) => {
  const { isAuthenticated, isInitializing, hasPermission } = useAuth();

  if (isInitializing) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Use the unified hasPermission function for all checks
  if (!hasPermission(permissions)) {
    return <Navigate to="/unauthorized" replace />;
  }

  return children;
};

export default ProtectedRoute;
