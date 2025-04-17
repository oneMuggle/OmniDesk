import { createBrowserRouter, Navigate } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';
import GuestRoute from '../components/GuestRoute';
import UnauthorizedPage from '../components/UnauthorizedPage';
import App from '../App';
import CalendarPage from '../components/CalendarPage';
import SettingsPage from '../components/SettingsPage';
import DeepSeekChatPage from '../components/DeepSeekChatPage';
import EventsPage from '../components/EventsPage'; 
import ProfilePage from '../components/ProfilePage';
import Login from '../components/Login';
import Register from '../components/Register';
import DocumentsPage from '../components/DocumentsPage';
import AnnouncementsPage from '../components/AnnouncementsPage';
import TrialsPage from '../components/TrialsPage';
import PersonnelPage from '../components/PersonnelPage';
import EquipmentPage from '../components/EquipmentPage';
import FileAnalysisPage from '../components/FileAnalysisPage';

const router = createBrowserRouter([
{
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Navigate to="calendar" replace /> },
      { path: "calendar", element: <GuestRoute><CalendarPage /></GuestRoute> },
      { 
        path: "settings", 
        element: <ProtectedRoute requiredPermissions={['users.manage_settings']}><SettingsPage /></ProtectedRoute> 
      },
      { 
        path: "events", 
        element: <ProtectedRoute requiredPermissions={['events.view_schedule', 'events.add_schedule', 'events.change_schedule', 'events.delete_schedule']}><EventsPage /></ProtectedRoute> 
      },
      { 
        path: "trials", 
        element: <ProtectedRoute requiredPermissions={['events.view_trial', 'events.add_trial', 'events.change_trial', 'events.delete_trial']}><TrialsPage /></ProtectedRoute> 
      },
      { 
        path: "personnel", 
        element: <ProtectedRoute requiredPermissions={['events.view_personnel', 'events.add_personnel', 'events.change_personnel', 'events.delete_personnel']}><PersonnelPage /></ProtectedRoute> 
      },
      { 
        path: "equipment", 
        element: <ProtectedRoute requiredPermissions={['events.view_equipment', 'events.add_equipment', 'events.change_equipment', 'events.delete_equipment']}><EquipmentPage /></ProtectedRoute>
      },
      { 
        path: "profile", 
        element: <ProtectedRoute><ProfilePage /></ProtectedRoute> 
      },
      { 
        path: "documents", 
        element: <ProtectedRoute requiredPermissions={['users.manage_documents']}><DocumentsPage /></ProtectedRoute> 
      },
      { 
        path: "announcements", 
        element: <ProtectedRoute requiredPermissions={['manage_announcements']}><AnnouncementsPage /></ProtectedRoute> 
      },
      { 
        path: "deepseek-chat", 
        element: <ProtectedRoute requiredPermissions={['use_ai_chat']}><DeepSeekChatPage /></ProtectedRoute> 
      },
      { 
        path: "file-analysis", 
        element: <ProtectedRoute requiredPermissions={['analyze_files']}><FileAnalysisPage /></ProtectedRoute> 
      }
    ]
  },
  {
    path: "/login",
    element: <Login />
  },
  {
    path: "/register",
    element: <Register />
  },
  {
    path: "/unauthorized",
    element: <UnauthorizedPage />
  },
], { basename: "/" });

export default router;
