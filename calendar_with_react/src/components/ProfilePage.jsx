import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/personnel';
import { useAuth } from '../context/AuthContext';

const ProfilePage = () => {
  const { user } = useAuth();
  const [profileData, setProfileData] = useState(null);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const response = await apiClient.get('/api/users/me/');
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
            <p>用户名: {profileData.username}</p>
            <p>邮箱: {profileData.email}</p>
            {/* 添加更多个人资料字段 */}
          </div>
        ) : (
          <p>加载中...</p>
        )}
      </div>
    </div>
  );
};

export default ProfilePage;
