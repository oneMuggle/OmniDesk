import React from 'react';
import PropTypes from 'prop-types';
import apiClient from '../../api/apiClient';

const ProfileSidebar = ({ activeSection, setActiveSection, userData }) => {
  const defaultAvatar = '/default-avatar.svg'; // Path to the new SVG in the public folder

  const getFullAvatarUrl = (avatarPath) => {
    if (!avatarPath) {
      return defaultAvatar;
    }
    // apiClient.defaults.baseURL is 'http://localhost:8000/api' or '/api' in prod.
    // We need the root of the backend URL for media files, which doesn't include '/api'.
    const backendRoot = apiClient.defaults.baseURL.replace(/\/api$/, '');
      
    return `${backendRoot}${avatarPath}`;
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

ProfileSidebar.propTypes = {
  activeSection: PropTypes.string.isRequired,
  setActiveSection: PropTypes.func.isRequired,
  userData: PropTypes.object,
};

ProfileSidebar.defaultProps = {
  userData: null,
};

export default ProfileSidebar;