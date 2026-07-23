import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import Register from './Register';
import { useAuth } from '../context/AuthContext';

jest.mock('../context/AuthContext', () => ({
  useAuth: jest.fn(),
}));

jest.mock('react-router-dom', () => ({
  ...jest.requireActual('react-router-dom'),
  useNavigate: jest.fn(),
}));

describe('Register Component', () => {
  let register;
  let navigate;
  let user;

  beforeEach(() => {
    register = jest.fn();
    navigate = jest.fn();
    useAuth.mockReturnValue({ register });
    useNavigate.mockReturnValue(navigate);
    user = userEvent.setup();
  });

  it('should render registration form', () => {
    render(<MemoryRouter><Register /></MemoryRouter>);
    expect(screen.getByPlaceholderText('用户名')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('密码')).toBeInTheDocument();
    expect(screen.getAllByPlaceholderText('确认密码')[0]).toBeInTheDocument();
    expect(screen.getByRole('button')).toBeInTheDocument();
  });

  it('should show error message on failed registration', async () => {
    register.mockResolvedValue({ success: false, errors: { username: ['A user with that username already exists.'] } });
    render(<MemoryRouter><Register /></MemoryRouter>);

    await user.type(screen.getByPlaceholderText('用户名'), 'existinguser');
    await user.type(screen.getByPlaceholderText('密码'), 'password');
    await user.type(screen.getAllByPlaceholderText('确认密码')[0], 'password');
    await user.click(screen.getByRole('button'));

    expect(await screen.findByText('A user with that username already exists.')).toBeInTheDocument();
  });

  it('should navigate to login page on successful registration', async () => {
    register.mockResolvedValue({ success: true });
    render(<MemoryRouter><Register /></MemoryRouter>);

    await user.type(screen.getByPlaceholderText('用户名'), 'newuser');
    await user.type(screen.getByPlaceholderText('密码'), 'password');
    await user.type(screen.getAllByPlaceholderText('确认密码')[0], 'password');
    await user.click(screen.getByRole('button'));

    await waitFor(() => {
      expect(navigate).toHaveBeenCalledWith('/login', {
        state: { registeredUsername: 'newuser' },
      });
    });
  });
});