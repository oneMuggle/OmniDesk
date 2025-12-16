import React from 'react';
import { render, screen } from '@testing-library/react';
import PropTypes from 'prop-types';
import { AuthContext, AuthProvider } from './AuthContext';

const TestComponent = ({ requiredPermission }) => {
  const { hasPermission } = React.useContext(AuthContext);
  return (
    <div>
      {hasPermission(requiredPermission) ? 'Has Permission' : 'No Permission'}
    </div>
  );
};

TestComponent.propTypes = {
  requiredPermission: PropTypes.string,
};

describe('AuthContext - hasPermission', () => {
  test('should return true if user has the required permission', () => {
    const user = { permissions: ['users.add_customuser'] };
    render(
      <AuthContext.Provider value={{ user, hasPermission: (required) => user.permissions.includes(required) }}>
        <TestComponent requiredPermission="users.add_customuser" />
      </AuthContext.Provider>
    );
    expect(screen.getByText('Has Permission')).toBeInTheDocument();
  });

  test('should return false if user does not have the required permission', () => {
    const user = { permissions: ['users.view_customuser'] };
    render(
      <AuthContext.Provider value={{ user, hasPermission: (required) => user.permissions.includes(required) }}>
        <TestComponent requiredPermission="some.missing_permission" />
      </AuthContext.Provider>
    );
    expect(screen.getByText('No Permission')).toBeInTheDocument();
  });

  test('should return true if no permission is required', () => {
    const user = { permissions: ['users.view_customuser'] };
    render(
      <AuthContext.Provider value={{ user, hasPermission: (required) => !required || user.permissions.includes(required) }}>
        <TestComponent />
      </AuthContext.Provider>
    );
    expect(screen.getByText('Has Permission')).toBeInTheDocument();
  });

  test('should return false if user has no permissions at all', () => {
    const user = { permissions: [] };
    render(
      <AuthContext.Provider value={{ user, hasPermission: (required) => user.permissions.includes(required) }}>
        <TestComponent requiredPermission="any.permission" />
      </AuthContext.Provider>
    );
    expect(screen.getByText('No Permission')).toBeInTheDocument();
  });
});
