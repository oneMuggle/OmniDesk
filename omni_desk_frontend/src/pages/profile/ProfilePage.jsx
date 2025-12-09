import React, { useState, useEffect } from 'react';
import ProfileSidebar from '../../components/profile/ProfileSidebar';
import EditProfileForm from '../../components/profile/EditProfileForm';
import ChangePasswordForm from '../../components/profile/ChangePasswordForm';
import '../../components/profile/ProfilePage.css';
import { notifications } from '../../utils/notifications';
import apiClient from '../../api/apiClient';

const ProfilePage = () => {
  const [activeSection, setActiveSection] = useState('editProfile');
  const [userData, setUserData] = useState(null); // Use null for initial loading state

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const response = await apiClient.get('/users/me/');
        setUserData(response.data);
      } catch (error) {
        notifications.showError('加载用户信息失败。');
        setUserData({}); // Set to empty object on error to avoid crash
      }
    };
    fetchUserData();
  }, []);

  // Render a loading state while data is being fetched
  if (userData === null) {
    return <div className="profile-page-container">正在加载个人资料...</div>;
  }

  return (
    <div className="profile-page-container">
      <ProfileSidebar 
        activeSection={activeSection} 
        setActiveSection={setActiveSection} 
        userData={userData} 
      />
      <div className="profile-content">
        {activeSection === 'editProfile' && <EditProfileForm userData={userData} setUserData={setUserData} />}
        {activeSection === 'changePassword' && <ChangePasswordForm />}
      </div>
    </div>
  );
};

export default ProfilePage;
