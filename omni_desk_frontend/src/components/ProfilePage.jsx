import React, { useEffect, useState } from 'react';
import apiClient from '../api/apiClient';
import { useAuth } from '../context/AuthContext';
import './ProfilePage.css';

const ProfilePage = () => {
  const { user } = useAuth();
  const [profileData, setProfileData] = useState(null);
  const [editMode, setEditMode] = useState(false);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    phone: '',
    real_name: '',
    avatar: null,
  });
  const [passwordData, setPasswordData] = useState({
    old_password: '',
    new_password: '',
  });

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await apiClient.get('/users/me/');
        setProfileData(response.data);
        setFormData({
          username: response.data.username,
          email: response.data.email,
          phone: response.data.phone || '',
          real_name: response.data.real_name || '',
          avatar: response.data.avatar,
        });
      } catch (error) {
        console.error('获取用户资料失败:', error);
      }
    };

    if (user) {
      fetchProfile();
    }
  }, [user]);

  const handleInputChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handlePasswordChange = (e) => {
    setPasswordData({ ...passwordData, [e.target.name]: e.target.value });
  };

  const handleFileChange = (e) => {
    setFormData({ ...formData, avatar: e.target.files[0] });
  };

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    const profileUpdateData = new FormData();
    profileUpdateData.append('username', formData.username);
    profileUpdateData.append('email', formData.email);
    profileUpdateData.append('phone', formData.phone);
    profileUpdateData.append('real_name', formData.real_name);
    if (formData.avatar instanceof File) {
      profileUpdateData.append('avatar', formData.avatar);
    }

    try {
      const response = await apiClient.patch('/users/me/update/', profileUpdateData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setProfileData(response.data);
      setEditMode(false);
    } catch (error) {
      console.error('更新用户资料失败:', error);
    }
  };

  const handleChangePassword = async (e) => {
    e.preventDefault();
    try {
      await apiClient.put('/users/me/change-password/', passwordData);
      alert('密码修改成功');
      setPasswordData({ old_password: '', new_password: '' });
    } catch (error) {
      console.error('修改密码失败:', error);
      alert('修改密码失败');
    }
  };

  return (
    <div className="page-container">
      <h2>个人资料</h2>
      <div className="profile-content">
        {profileData ? (
          <div>
            <div className="profile-header">
              <img src={formData.avatar || 'default-avatar.png'} alt="Avatar" className="avatar" />
              {editMode && <input type="file" onChange={handleFileChange} />}
            </div>
            <div className="basic-info">
              {editMode ? (
                <form onSubmit={handleProfileUpdate}>
                  <p>
                    用户名:
                    <input type="text" name="username" value={formData.username} onChange={handleInputChange} />
                  </p>
                  <p>
                    邮箱:
                    <input type="email" name="email" value={formData.email} onChange={handleInputChange} />
                  </p>
                  <p>
                    联系电话:
                    <input type="text" name="phone" value={formData.phone} onChange={handleInputChange} />
                  </p>
                  <p>
                    真实姓名:
                    <input
                      type="text"
                      name="real_name"
                      value={formData.real_name}
                      onChange={handleInputChange}
                      disabled={profileData?.personnel !== null} // 如果已关联人员，则禁用
                    />
                  </p>
                  <button type="submit">保存</button>
                  <button type="button" onClick={() => setEditMode(false)}>取消</button>
                </form>
              ) : (
                <div>
                  <p>用户名: {profileData.username}</p>
                  <p>邮箱: {profileData.email}</p>
                  <p>联系电话: {profileData.phone}</p>
                  <p>真实姓名: {profileData.real_name}</p>
                  <p>角色: <span className="role-badge">{profileData.role}</span></p>
                  <button onClick={() => setEditMode(true)}>编辑</button>
                </div>
              )}
            </div>
            <div className="change-password">
              <h3>修改密码</h3>
              <form onSubmit={handleChangePassword}>
                <input
                  type="password"
                  name="old_password"
                  placeholder="旧密码"
                  value={passwordData.old_password}
                  onChange={handlePasswordChange}
                />
                <input
                  type="password"
                  name="new_password"
                  placeholder="新密码"
                  value={passwordData.new_password}
                  onChange={handlePasswordChange}
                />
                <button type="submit">确认修改</button>
              </form>
            </div>
          </div>
        ) : (
          <p>加载中...</p>
        )}
      </div>
    </div>
  );
};

export default ProfilePage;
