import React, { useContext } from 'react';
import { render, screen, act } from '@testing-library/react';
import '@testing-library/jest-dom/extend-expect';
import { AuthProvider, AuthContext } from './AuthContext';

const TestComponent = () => {
  const { user, isAuthenticated, login, logout } = useContext(AuthContext);
  return (
    <div>
      <span data-testid="isAuthenticated">{isAuthenticated.toString()}</span>
      <span data-testid="user">{user ? user.username : 'null'}</span>
      <button onClick={() => login({ username: 'testuser' })}>Login</button>
      <button onClick={logout}>Logout</button>
    </div>
  );
};

const renderWithAuthProvider = () => {
  return render(
    <AuthProvider>
      <TestComponent />
    </AuthProvider>
  );
};

describe('AuthContext', () => {
  it('should have default values', () => {
    renderWithAuthProvider();
    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
    expect(screen.getByTestId('user')).toHaveTextContent('null');
  });

  it('should update state on login', () => {
    renderWithAuthProvider();
    act(() => {
      screen.getByText('Login').click();
    });
    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('true');
    expect(screen.getByTestId('user')).toHaveTextContent('testuser');
  });

  it('should update state on logout', () => {
    renderWithAuthProvider();
    act(() => {
      screen.getByText('Login').click();
    });
    act(() => {
      screen.getByText('Logout').click();
    });
    expect(screen.getByTestId('isAuthenticated')).toHaveTextContent('false');
    expect(screen.getByTestId('user')).toHaveTextContent('null');
  });
});
