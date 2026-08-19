/**
 * ChangePasswordForm 单测(R4-D2)。
 *
 * mock apiClient 与 notifications,覆盖:
 * 新密码不匹配短路 / 成功提交 / 接口失败反馈。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import apiClient from '../../../../shared/api/apiClient';
import { notifications } from '../../../../shared/utils/notifications';
import ChangePasswordForm from '../ChangePasswordForm';

jest.mock('../../../../shared/api/apiClient', () => ({
  __esModule: true,
  default: { post: jest.fn() },
}));

jest.mock('../../../../shared/utils/notifications', () => ({
  notifications: { showError: jest.fn(), showSuccess: jest.fn() },
}));

const fillForm = ({ oldValue, newValue, confirmValue }) => {
  fireEvent.change(screen.getByLabelText('旧密码'), { target: { value: oldValue } });
  fireEvent.change(screen.getByLabelText('新密码'), { target: { value: newValue } });
  fireEvent.change(screen.getByLabelText('确认新密码'), { target: { value: confirmValue } });
};

const submitForm = () => fireEvent.click(screen.getByRole('button', { name: '修改密码' }));

describe('ChangePasswordForm', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('渲染三个密码输入框与提交按钮', () => {
    render(<ChangePasswordForm />);

    expect(screen.getByLabelText('旧密码')).toBeInTheDocument();
    expect(screen.getByLabelText('新密码')).toBeInTheDocument();
    expect(screen.getByLabelText('确认新密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '修改密码' })).toBeInTheDocument();
  });

  it('新密码与确认密码不匹配 → 提示错误且不调用接口', async () => {
    render(<ChangePasswordForm />);

    fillForm({ oldValue: 'old1', newValue: 'new123', confirmValue: 'different' });
    submitForm();

    await waitFor(() => {
      expect(notifications.showError).toHaveBeenCalledWith('新密码不匹配。');
    });
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('提交成功 → 调用 change_password 接口并清空表单', async () => {
    apiClient.post.mockResolvedValue({});
    render(<ChangePasswordForm />);

    fillForm({ oldValue: 'old1', newValue: 'new123', confirmValue: 'new123' });
    submitForm();

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith('users/change_password/', {
        old_password: 'old1',
        new_password: 'new123',
      });
    });
    expect(notifications.showSuccess).toHaveBeenCalledWith('密码修改成功！');
    expect(screen.getByLabelText('旧密码')).toHaveValue('');
    expect(screen.getByLabelText('新密码')).toHaveValue('');
    expect(screen.getByLabelText('确认新密码')).toHaveValue('');
  });

  it('接口失败 → 提示失败文案', async () => {
    apiClient.post.mockRejectedValue(new Error('server down'));
    render(<ChangePasswordForm />);

    fillForm({ oldValue: 'old1', newValue: 'new123', confirmValue: 'new123' });
    submitForm();

    await waitFor(() => {
      expect(notifications.showError).toHaveBeenCalledWith('密码修改失败，请检查您的旧密码。');
    });
  });
});