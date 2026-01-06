import { useState, useEffect, useContext } from 'react';
import { AuthContext } from '../../auth/context/AuthContext';
import ProfileSidebar from '../components/ProfileSidebar';
import EditProfileForm from '../components/EditProfileForm';
import ChangePasswordForm from '../components/ChangePasswordForm';
import '../components/ProfilePage.css';
import { notifications } from '../../../shared/utils/notifications';
import apiClient from '../../../shared/api/apiClient';

const ProfilePage = () => {
  const { setUser: setAuthUser } = useContext(AuthContext);
  const [activeSection, setActiveSection] = useState('editProfile');
  const [userData, setUserData] = useState(null); // Use null for initial loading state

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        const response = await apiClient.get('users/me/');
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
        {activeSection === 'editProfile' && <EditProfileForm userData={userData} setUserData={(updatedUser) => {
          setUserData(updatedUser);
          setAuthUser(updatedUser);
        }} />}
        {activeSection === 'changePassword' && <ChangePasswordForm />}
      </div>
    </div>
  );
};

export default ProfilePage;
