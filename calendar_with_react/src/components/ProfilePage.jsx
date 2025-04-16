import React, { useEffect, useState } from 'react';
import { apiClient } from '../api/personnel';
import { useAuth } from '../context/AuthContext';
import './ProfilePage.css';

const PermissionGroup = ({ title, permissions }) => {
  const [isExpanded, setIsExpanded] = useState(true);
  
  return (
    <div className="permission-group">
      <h3 onClick={() => setIsExpanded(!isExpanded)} className="group-header">
        {title} ({permissions.length})
        <span className="toggle-icon">{isExpanded ? '▼' : '▶'}</span>
      </h3>
      {isExpanded && (
        <ul>
          {permissions.map((perm, index) => (
            <li key={index} className="permission-item">
              <span className="permission-code">{perm}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

const ProfilePage = () => {
  const { user } = useAuth();
  const [profileData, setProfileData] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');

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

  const groupPermissions = (permissions) => {
    const groups = {};
    permissions.forEach(perm => {
      const [app] = perm.split('.');
      if (!groups[app]) {
        groups[app] = [];
      }
      groups[app].push(perm);
    });
    return groups;
  };

  const filteredPermissions = profileData?.permissions?.permissions
    ? profileData.permissions.permissions.filter(perm => 
        perm.toLowerCase().includes(searchTerm.toLowerCase()))
    : [];

  const permissionGroups = groupPermissions(filteredPermissions);

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
            
            <div className="permissions-section">
              <div className="permissions-header">
                <h3>我的权限</h3>
                <input
                  type="text"
                  placeholder="搜索权限..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="permission-search"
                />
              </div>
              
              {Object.entries(permissionGroups).map(([group, perms]) => (
                <PermissionGroup 
                  key={group}
                  title={group}
                  permissions={perms}
                />
              ))}
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
