import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = ({ 
  children, 
  allowGuest = false, 
  requireAuth = false
}) => {
  const { isAuthenticated, isInitializing, isGuest } = useAuth();

  console.log('ProtectedRoute state:', {
    isAuthenticated,
    isInitializing, 
    isGuest,
    requireAuth,
    allowGuest
  });

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



  return children;
};

export default ProtectedRoute;
