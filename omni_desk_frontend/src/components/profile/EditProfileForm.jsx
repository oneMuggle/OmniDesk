import React, { useState } from 'react';
import apiClient from '../../api/apiClient';
import { notifications } from '../../utils/notifications';
import './ProfileForms.css';

const EditProfileForm = ({ userData, setUserData }) => {
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setUserData(prev => ({ ...prev, [name]: value }));
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setUserData(prev => ({ ...prev, avatar: file }));
    }
  };

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    const formData = new FormData();

    // Iterate over userData and append to formData
    Object.keys(userData).forEach(key => {
      const value = userData[key];
      
      if (key === 'avatar') {
        // CRITICAL FIX: Only append the avatar if it's a File object (a new upload)
        if (value instanceof File) {
          formData.append(key, value);
        }
      } else {
        // Append all other fields as usual
        if (value !== null && value !== undefined) {
          formData.append(key, value);
        }
      }
    });

    try {
      const response = await apiClient.patch('/users/me/update/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setUserData(response.data);
      notifications.showSuccess('个人资料更新成功！');
    } catch (error) {
      notifications.showError('个人资料更新失败。');
    } finally {
      setLoading(false);
    }
  };

  if (!userData) {
    return <div>正在加载表单...</div>;
  }

  return (
    <form onSubmit={handleProfileUpdate} className="profile-form">
      <div className="form-group">
        <label htmlFor="real_name">真实姓名</label>
        <input
          type="text"
          id="real_name"
          name="real_name"
          value={userData.real_name || ''}
          onChange={handleChange}
        />
      </div>
      <div className="form-group">
        <label htmlFor="email">电子邮箱</label>
        <input
          type="email"
          id="email"
          name="email"
          value={userData.email || ''}
          onChange={handleChange}
        />
      </div>
      <div className="form-group">
        <label htmlFor="avatar">头像</label>
        <input
          type="file"
          id="avatar"
          name="avatar"
          onChange={handleFileChange}
        />
      </div>
      <button type="submit" disabled={loading}>
        {loading ? '正在保存...' : '保存更改'}
      </button>
    </form>
  );
};

export default EditProfileForm;