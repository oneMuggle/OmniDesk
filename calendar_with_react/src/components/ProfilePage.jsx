import React, { useEffect, useState } from 'react';
import apiClient from '../api/apiClient';
import { useAuth } from '../context/AuthContext';
import './ProfilePage.css';

const ProfilePage = () => {
  const { user } = useAuth();
  const [profileData, setProfileData] = useState(null);
  

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await apiClient.get('/users/me/');
        setProfileData(response.data);
      } catch (error) {
        console.error('获取用户资料失败:', error);
      }
    };

    if (user) {
      fetchProfile();
    }
  }, [user]);

  

  return (
    <div className="page-container">
      <h2>个人资料</h2>
      <div className="profile-content">
        {profileData ? (
          <div>
            <div className="basic-info">
              <p>用户名: {profileData.username}</p>
              <p>邮箱: {profileData.email}</p>
              {profileData.permissions?.role && (
                <p>角色: <span className="role-badge">{profileData.permissions.role}</span></p>
              )}
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
