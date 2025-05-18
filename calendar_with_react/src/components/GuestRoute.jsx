import React from 'react';
import ProtectedRoute from './ProtectedRoute';

const GuestRoute = ({ children, ...props }) => {
  return (
    <ProtectedRoute 
      {...props}
      allowGuest={true}
    >
      {React.cloneElement(children, { isGuest: true })}
    </ProtectedRoute>
  );
};

export default GuestRoute;
