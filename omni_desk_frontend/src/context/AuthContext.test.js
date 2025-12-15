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
      <AuthProvider value={{ user }}>
        <TestComponent requiredPermission="users.add_customuser" />
      </AuthProvider>
    );
    expect(screen.getByText('Has Permission')).toBeInTheDocument();
  });

  test('should return false if user does not have the required permission', () => {
    const user = { permissions: ['users.view_customuser'] };
    render(
      <AuthProvider value={{ user }}>
        <TestComponent requiredPermission="some.missing_permission" />
      </AuthProvider>
    );
    expect(screen.getByText('No Permission')).toBeInTheDocument();
  });

  test('should return true if no permission is required', () => {
    const user = { permissions: ['users.view_customuser'] };
    render(
      <AuthProvider value={{ user }}>
        <TestComponent />
      </AuthProvider>
    );
    expect(screen.getByText('Has Permission')).toBeInTheDocument();
  });

  test('should return false if user has no permissions at all', () => {
    const user = { permissions: [] };
    render(
      <AuthProvider value={{ user }}>
        <TestComponent requiredPermission="any.permission" />
      </AuthProvider>
    );
    expect(screen.getByText('No Permission')).toBeInTheDocument();
  });
});
