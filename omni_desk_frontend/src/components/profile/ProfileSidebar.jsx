import React from 'react';

const ProfileSidebar = ({ activeSection, setActiveSection, userData }) => {
  const defaultAvatar = '/default-avatar.svg'; // Path to the new SVG in the public folder

  const getFullAvatarUrl = (avatarPath) => {
    if (!avatarPath) {
      return defaultAvatar;
    }
    const baseUrl = process.env.NODE_ENV === 'production' 
      ? '' 
      : (process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000');
      
    return `${baseUrl}${avatarPath}`;
  };

  return (
    <div className="profile-sidebar">
      <div className="user-info">
        <img 
          src={getFullAvatarUrl(userData.avatar)} 
          alt="Avatar" 
          className="profile-avatar" 
          onError={(e) => {
            // Prevent infinite loop if the default avatar itself is broken
            if (e.target.src !== `${window.location.origin}${defaultAvatar}`) {
              e.target.onerror = null; 
              e.target.src = defaultAvatar;
            }
          }}
        />
        <h3>{userData.real_name || '用户'}</h3>
        <p>{userData.role || '角色'}</p>
      </div>
      <ul className="profile-menu">
        <li
          className={activeSection === 'editProfile' ? 'active' : ''}
          onClick={() => setActiveSection('editProfile')}
        >
          编辑资料
        </li>
        <li
          className={activeSection === 'changePassword' ? 'active' : ''}
          onClick={() => setActiveSection('changePassword')}
        >
          修改密码
        </li>
      </ul>
    </div>
  );
};

export default ProfileSidebar;