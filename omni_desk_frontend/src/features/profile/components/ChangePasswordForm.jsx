import { useState } from 'react';
import apiClient from '../../../shared/api/apiClient';
import { notifications } from '../../../shared/utils/notifications';
import './ProfileForms.css';

const ChangePasswordForm = () => {
  const [passwordData, setPasswordData] = useState({
    old_password: '',
    new_password: '',
    confirm_password: '',
  });
  const [loading, setLoading] = useState(false);

  const handlePasswordChange = (e) => {
    const { name, value } = e.target;
    setPasswordData((prev) => ({ ...prev, [name]: value }));
  };

  const handleChangePasswordSubmit = async (e) => {
    e.preventDefault();
    if (passwordData.new_password !== passwordData.confirm_password) {
      notifications.showError("新密码不匹配。");
      return;
    }
    setLoading(true);
    try {
      await apiClient.post('/api/users/change_password/', {
        old_password: passwordData.old_password,
        new_password: passwordData.new_password,
      });
      notifications.showSuccess('密码修改成功！');
      setPasswordData({ old_password: '', new_password: '', confirm_password: '' });
    } catch (error) {
      notifications.showError('密码修改失败，请检查您的旧密码。');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleChangePasswordSubmit} className="profile-form">
      <div className="form-group">
        <label htmlFor="old_password">旧密码</label>
        <input
          type="password"
          id="old_password"
          name="old_password"
          value={passwordData.old_password}
          onChange={handlePasswordChange}
          required
        />
      </div>
      <div className="form-group">
        <label htmlFor="new_password">新密码</label>
        <input
          type="password"
          id="new_password"
          name="new_password"
          value={passwordData.new_password}
          onChange={handlePasswordChange}
          required
        />
      </div>
      <div className="form-group">
        <label htmlFor="confirm_password">确认新密码</label>
        <input
          type="password"
          id="confirm_password"
          name="confirm_password"
          value={passwordData.confirm_password}
          onChange={handlePasswordChange}
          required
        />
      </div>
      <button type="submit" disabled={loading}>
        {loading ? '正在修改...' : '修改密码'}
      </button>
    </form>
  );
};

export default ChangePasswordForm;