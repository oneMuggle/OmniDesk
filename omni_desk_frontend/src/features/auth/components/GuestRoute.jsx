import React from 'react';
import PropTypes from 'prop-types';
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

GuestRoute.propTypes = {
  children: PropTypes.node.isRequired,
};

export default GuestRoute;
