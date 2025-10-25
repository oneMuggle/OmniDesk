import { createBrowserRouter, Navigate } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';
import GuestRoute from '../components/GuestRoute';
import UnauthorizedPage from '../components/UnauthorizedPage';
import App from '../App';
import SchedulePage from '../components/SchedulePage';
import SettingsPage from '../pages/SettingsPage';
import IntelligentChatPage from '../components/IntelligentChatPage';
import RagflowChatPage from '../components/RagflowChatPage';
import EventsPage from '../components/EventsPage';
import AdminLayout from '../components/Admin/AdminLayout';
import ProfilePage from '../components/ProfilePage';
import Login from '../components/Login';
import Register from '../components/Register';
import DocumentsPage from '../components/DocumentsPage';
import AnnouncementsPage from '../components/AnnouncementsPage';
import EquipmentPage from '../components/EquipmentPage';
import FileAnalysisPage from '../components/FileAnalysisPage';
import DocsPage from '../components/DocsPage';
import BookPage from '../components/BookPage';
import BookReaderPage from '../components/BookReaderPage';
import LibraryPage from '../components/LibraryPage';
import BookImportPage from '../components/BookImportPage';
import ChapterEditorPage from '../components/ChapterEditorPage'; // 导入 ChapterEditorPage
import TrialsPage from '../components/TrialsPage';
import PersonnelPage from '../components/PersonnelPage';
import BookManageExportPage from '../components/BookManageExportPage';
import TrialScheduleContainer from '../components/TrialScheduleContainer';
import ShiftScheduleContainer from '../components/ShiftScheduleContainer';
import WelcomePage from '../pages/WelcomePage'; // 导入 WelcomePage
import MemoPage from '../pages/MemoPage'; // 导入 MemoPage
import ManageAnnouncementsPage from '../components/ManageAnnouncementsPage';
import AnnouncementForm from '../components/AnnouncementForm';
import DifyAppList from '../components/DifyApps/DifyAppList';
import DifyAppViewer from '../components/DifyApps/DifyAppViewer';
import DifyAppManagementPage from '../components/DifyApps/DifyAppManagementPage';
import ScheduleManagementPage from '../pages/ScheduleManagementPage';
import ScheduleSettingsPage from '../components/ScheduleSettingsPage';
import OfficeAssistant from '../components/OfficeAssistant/OfficeAssistant';
import ProjectsPage from '../pages/ProjectsPage'; // Import ProjectsPage
import CompliancePage from '../pages/CompliancePage'; // Import CompliancePage
import NotificationsPage from '../pages/NotificationsPage'; // Import NotificationsPage
import MeetingRoomBookingPage from '../pages/MeetingRoomBookingPage'; // Import MeetingRoomBookingPage
import MeetingRoomManagementPage from '../pages/MeetingRoomManagementPage'; // Import MeetingRoomManagementPage
import AdminUserManagementPage from '../pages/AdminUserManagementPage'; // Import AdminUserManagementPage
import UserPersonnelManagementPage from '../pages/UserPersonnelManagementPage'; // 导入新页面
import SensorManagementPage from '../pages/SensorManagementPage'; // 导入 SensorManagementPage
import SensorCategoryManagementPage from '../pages/SensorCategoryManagementPage'; // 导入 SensorCategoryManagementPage
import StorageLocationManagementPage from '../pages/StorageLocationManagementPage'; // 导入 StorageLocationManagementPage
import SensorCalibrationManagementPage from '../pages/SensorCalibrationManagementPage'; // 导入 SensorCalibrationManagementPage

const router = createBrowserRouter([
{
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: (
          <ProtectedRoute> {/* 使用 ProtectedRoute 判断登录状态 */}
            <WelcomePage />
          </ProtectedRoute>
        ),
      },
      {
        path: "meeting-rooms",
        element: <ProtectedRoute pagePath="/meeting-rooms"><MeetingRoomBookingPage /></ProtectedRoute>
      },
      { path: "schedule", element: <GuestRoute><SchedulePage /></GuestRoute> },
      { path: "trial-schedule", element: <GuestRoute><TrialScheduleContainer /></GuestRoute> },
      { path: "shift-schedule", element: <GuestRoute><ShiftScheduleContainer /></GuestRoute> },
      {
        path: "events",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/events"><EventsPage /></ProtectedRoute>
      },
      {
        path: "equipment",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/equipment"><EquipmentPage /></ProtectedRoute>
      },
      {
        path: "profile",
        element: <ProtectedRoute pagePath="/profile"><ProfilePage /></ProtectedRoute>
      },
      {
        path: "library", // 新增书库路由
        element: <LibraryPage />
      },
      {
        path: "books/:bookId", // 动态书籍详情路由
        element: <BookPage />
      },
      {
        path: "announcements",
        element: <ProtectedRoute pagePath="/announcements"><AnnouncementsPage /></ProtectedRoute>
      },
      {
        path: "intelligent-chat",
        element: <ProtectedRoute pagePath="/intelligent-chat"><IntelligentChatPage /></ProtectedRoute>
      },
      {
        path: "ragflow-chat",
        element: <ProtectedRoute pagePath="/ragflow-chat"><RagflowChatPage /></ProtectedRoute>
      },
      {
        path: "file-analysis",
        element: <ProtectedRoute pagePath="/file-analysis"><FileAnalysisPage /></ProtectedRoute>
      },
      {
        path: "docs/cdepsio6",
        element: <ProtectedRoute pagePath="/docs/cdepsio6"><DocsPage /></ProtectedRoute>
      },
      {
        path: "books/:bookId/:chapterId/edit", // 新增章节编辑路由
        element: <ProtectedRoute roles={['admin']}><ChapterEditorPage /></ProtectedRoute> // 只有管理员可以访问
      },
      {
        path: "memos", // 新增备忘录路由
        element: <ProtectedRoute pagePath="/memos"><MemoPage /></ProtectedRoute>
      },
      {
        path: "dify-apps",
        element: <ProtectedRoute pagePath="/dify-apps"><DifyAppList /></ProtectedRoute>
      },
      {
        path: "dify-apps/:appId",
        element: <ProtectedRoute pagePath="/dify-apps/:appId"><DifyAppViewer /></ProtectedRoute>
      },
      {
        path: "office-assistant",
        element: <ProtectedRoute pagePath="/office-assistant"><OfficeAssistant /></ProtectedRoute>
      },
      {
        path: "projects", // Move ProjectsPage to root level
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/projects"><ProjectsPage /></ProtectedRoute>
      },
      {
        path: "notifications", // Add NotificationsPage to root level
        element: <ProtectedRoute pagePath="/notifications"><NotificationsPage /></ProtectedRoute>
      },
      {
        path: "documents", // 将 DocumentsPage 移动到主页面路由
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/documents"><DocumentsPage /></ProtectedRoute>
      },
      {
        path: "sensor-management", // 新增传感器管理路由
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/sensor-management"><SensorManagementPage /></ProtectedRoute>
      },
      {
        path: "sensor-categories", // 新增传感器类别管理路由
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/sensor-categories"><SensorCategoryManagementPage /></ProtectedRoute>
      },
      {
        path: "storage-locations", // 新增存放位置管理路由
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/storage-locations"><StorageLocationManagementPage /></ProtectedRoute>
      },
      {
        path: "sensor-calibration/:id", // 新增传感器校准管理路由，:id 为动态参数
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/sensor-calibration/:id"><SensorCalibrationManagementPage /></ProtectedRoute>
      }
    ]
  },
  {
    path: "/admin",
    element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin"><AdminLayout /></ProtectedRoute>,
    children: [
      { index: true, element: <Navigate to="trials" replace /> },
      {
        path: "trials",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/trials"><TrialsPage /></ProtectedRoute>
      },
      {
        path: "personnel",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/personnel"><PersonnelPage /></ProtectedRoute>
      },
      {
        path: "schedules",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/schedules"><ScheduleManagementPage /></ProtectedRoute>
      },
      {
        path: "book-import",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/book-import"><BookImportPage /></ProtectedRoute>
      },
      {
        path: "book-manage-export",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/book-manage-export"><BookManageExportPage /></ProtectedRoute>
      },
      {
        path: "equipment",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/equipment"><EquipmentPage /></ProtectedRoute>
      },
      {
        path: "settings",
        element: <ProtectedRoute pagePath="/admin/settings"><SettingsPage /></ProtectedRoute>
      },
      {
        path: "announcements",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/announcements"><ManageAnnouncementsPage /></ProtectedRoute>
      },
      {
        path: "announcements/new",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/announcements/new"><AnnouncementForm /></ProtectedRoute>
      },
      {
        path: "announcements/edit/:id",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/announcements/edit/:id"><AnnouncementForm /></ProtectedRoute>
      },
      {
        path: "dify-app-management",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/dify-app-management"><DifyAppManagementPage /></ProtectedRoute>
      },
      {
        path: "schedule-settings",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/schedule-settings"><ScheduleSettingsPage /></ProtectedRoute>
      },
      {
        path: "compliance", // Add CompliancePage route under /admin
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/compliance"><CompliancePage /></ProtectedRoute>
      },
      {
        path: "meeting-room-management",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/meeting-room-management"><MeetingRoomManagementPage /></ProtectedRoute>
      },
      {
        path: "user-management",
        element: <ProtectedRoute roles={['admin']} pagePath="/admin/user-management"><AdminUserManagementPage /></ProtectedRoute>
      },
      {
        path: "user-personnel-management",
        element: <ProtectedRoute roles={['admin', 'manager']} pagePath="/admin/user-personnel-management"><UserPersonnelManagementPage /></ProtectedRoute>
      },
      {
       path: "settings",
       element: <ProtectedRoute pagePath="/admin/settings"><SettingsPage /></ProtectedRoute>
     }
    ]
  },
  {
    path: "/read-book/:bookId", // 新增独立书籍阅读路由
    element: <BookReaderPage />
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

