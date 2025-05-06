import React from 'react';
import { useAuth } from '../context/AuthContext';

const GuestRoute = ({ children }) => {
  const { isInitializing } = useAuth();

  if (isInitializing) {
    return <div>Loading...</div>;
  }

  return React.cloneElement(children, { isGuest: true });
};

export default GuestRoute;
