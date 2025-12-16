import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { MemoryRouter } from 'react-router-dom';
import Register from './Register';
import { register } from '../api/userManagementApi';

jest.mock('../api/userManagementApi', () => ({
  register: jest.fn(),
}));

describe('Register Component', () => {
  beforeEach(() => {
    register.mockClear();
  });

  it('should render registration form', () => {
    render(<MemoryRouter><Register /></MemoryRouter>);
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Email')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /注册/i })).toBeInTheDocument();
  });

  it('should show error message on failed registration', async () => {
    register.mockResolvedValue({ success: false, errors: { username: ['A user with that username already exists.'] } });
    render(<MemoryRouter><Register /></MemoryRouter>);

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'existinguser' } });
    fireEvent.change(screen.getByPlaceholderText('Email'), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password' } });
    fireEvent.click(screen.getByRole('button', { name: /注册/i }));

    expect(await screen.findByText('A user with that username already exists.')).toBeInTheDocument();
  });

  it('should show success message on successful registration', async () => {
    register.mockResolvedValue({ success: true });
    render(<MemoryRouter><Register /></MemoryRouter>);

    fireEvent.change(screen.getByPlaceholderText('用户名'), { target: { value: 'newuser' } });
    fireEvent.change(screen.getByPlaceholderText('Email'), { target: { value: 'new@example.com' } });
    fireEvent.change(screen.getByPlaceholderText('密码'), { target: { value: 'password' } });
    fireEvent.click(screen.getByRole('button', { name: /注册/i }));

    await waitFor(() => {
      expect(register).toHaveBeenCalled();
    });
  });
});