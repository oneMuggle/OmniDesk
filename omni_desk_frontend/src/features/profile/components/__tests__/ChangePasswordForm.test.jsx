/**
 * ChangePasswordForm 单测(R4-D2)。
 *
 * mock apiClient 与 notifications,覆盖:
 * 新密码不匹配短路 / 成功提交 / 接口失败反馈。
 *
 * Contract anchor(防止路径漂移):后端 users/urls.py 的 change-password
 * 路由是 path("me/change-password/", ChangePasswordView),ChangePasswordView
 * 继承 UpdateAPIView,支持 PUT/PATCH。任何"省略 me"或"POST"的写法都会
 * 拿到 404 / 405,后端 test_auth_flow.py:test_change_password_success
 * 也用 PUT。这是该组件的接口契约。
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import apiClient from '../../../../shared/api/apiClient';
import { notifications } from '../../../../shared/utils/notifications';
import ChangePasswordForm from '../ChangePasswordForm';

jest.mock('../../../../shared/api/apiClient', () => ({
  __esModule: true,
  default: { put: jest.fn(), post: jest.fn() },
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
    expect(apiClient.put).not.toHaveBeenCalled();
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('提交成功 → 调用 PUT users/me/change-password/ 并清空表单', async () => {
    apiClient.put.mockResolvedValue({});
    render(<ChangePasswordForm />);

    fillForm({ oldValue: 'old1', newValue: 'new123', confirmValue: 'new123' });
    submitForm();

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('users/me/change-password/', {
        old_password: 'old1',
        new_password: 'new123',
      });
    });
    expect(apiClient.post).not.toHaveBeenCalled();
    expect(notifications.showSuccess).toHaveBeenCalledWith('密码修改成功！');
    expect(screen.getByLabelText('旧密码')).toHaveValue('');
    expect(screen.getByLabelText('新密码')).toHaveValue('');
    expect(screen.getByLabelText('确认新密码')).toHaveValue('');
  });

  it('接口失败 → 提示失败文案', async () => {
    apiClient.put.mockRejectedValue(new Error('server down'));
    render(<ChangePasswordForm />);

    fillForm({ oldValue: 'old1', newValue: 'new123', confirmValue: 'new123' });
    submitForm();

    await waitFor(() => {
      expect(notifications.showError).toHaveBeenCalledWith('密码修改失败，请检查您的旧密码。');
    });
  });

  // ─── 契约回归测试:防止 ChangePasswordForm 重新引入错误的 URL/方法 ──────
  it('源码不调用错误的 change_password 接口路径', async () => {
    // 该测试通过 mock 拦截真实请求,确保它没退化到老的下划线路径
    // (这能拦截"后人凭印象改回 change_password/"的回归)。
    apiClient.put.mockResolvedValue({});
    render(<ChangePasswordForm />);
    fillForm({ oldValue: 'a', newValue: 'b', confirmValue: 'b' });
    submitForm();

    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalled();
    });
    // 任何带下划线的旧路径都不应被调用
    for (const call of apiClient.put.mock.calls) {
      const url = call[0];
      expect(url).not.toMatch(/change_password/);
      expect(url).toMatch(/me\/change-password\/?$/);
    }
    // POST 永远不应被调用 — 这是 UpdateAPIView,不是 CreateAPIView
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});