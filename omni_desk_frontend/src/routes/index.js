import React from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import ProtectedRoute from '../components/ProtectedRoute';
import GuestRoute from '../components/GuestRoute';
import UnauthorizedPage from '../pages/UnauthorizedPage';
import App from '../App';
import SchedulePage from '../pages/SchedulePage';
import SystemSettingsPage from '../pages/SystemSettingsPage';
import IntelligentChatPage from '../pages/IntelligentChatPage';
import RagflowChatPage from '../pages/RagflowChatPage';
import EventsPage from '../pages/EventsPage';
import AdminLayout from '../components/Admin/AdminLayout';
import ProfilePage from '../pages/profile/ProfilePage';
import PersonnelDetailPage from '../pages/PersonnelDetailPage';
import Login from '../pages/Login';
import Register from '../pages/Register';
import DocumentsPage from '../pages/DocumentsPage';
import AnnouncementsPage from '../pages/AnnouncementsPage';
import EquipmentPage from '../pages/EquipmentPage';
import FileAnalysisPage from '../pages/FileAnalysisPage';
import DocsPage from '../pages/DocsPage';
import BookPage from '../pages/BookPage';
import BookReaderPage from '../pages/BookReaderPage';
import LibraryPage from '../pages/LibraryPage';
import ChapterEditorPage from '../pages/ChapterEditorPage'; // 导入 ChapterEditorPage
import TrialsPage from '../pages/TrialsPage';
import PersonnelManagementPage from '../pages/PersonnelManagementPage';
import PersonnelEditPage from '../pages/PersonnelEditPage';
import TrialScheduleContainer from '~/features/schedule/components/TrialScheduleContainer';
import ShiftScheduleContainer from '../components/ShiftScheduleContainer';
import DashboardPage from '../pages/DashboardPage'; // 导入 DashboardPage
import MemoPage from '../pages/MemoPage'; // 导入 MemoPage
import ManageAnnouncementsPage from '../pages/ManageAnnouncementsPage';
import AnnouncementForm from '../components/AnnouncementForm';
import DifyAppList from '../pages/DifyApps/DifyAppList';
import DifyAppViewer from '../pages/DifyApps/DifyAppViewer';
import DifyAppManagementPage from '../pages/DifyApps/DifyAppManagementPage';
import ScheduleManagementPage from '~/features/schedule/pages/ScheduleManagementPage';
import ScheduleSettingsPage from '../pages/ScheduleSettingsPage';
import OfficeAssistant from '../pages/OfficeAssistant/OfficeAssistant';
import ProjectsPage from '../pages/ProjectsPage'; // Import ProjectsPage
import CompliancePage from '../pages/CompliancePage'; // Import CompliancePage
import NotificationsPage from '../pages/NotificationsPage'; // Import NotificationsPage
import MeetingRoomBookingPage from '../pages/MeetingRoomBookingPage'; // Import MeetingRoomBookingPage
import MeetingRoomManagementPage from '../pages/MeetingRoomManagementPage'; // Import MeetingRoomManagementPage
import UserManagementPage from '../pages/UserManagementPage'; // Import UserManagementPage
import SensorManagementPage from '../pages/SensorManagementPage'; // 导入 SensorManagementPage
import SensorCategoryManagementPage from '../pages/SensorCategoryManagementPage'; // 导入 SensorCategoryManagementPage
import StorageLocationManagementPage from '../pages/StorageLocationManagementPage'; // 导入 StorageLocationManagementPage
import SensorCalibrationManagementPage from '../pages/SensorCalibrationManagementPage'; // 导入 SensorCalibrationManagementPage
import SensorDetailPage from '../pages/SensorDetailPage'; // 导入 SensorDetailPage
import EBookManagementPage from '../pages/EBookManagementPage'; // 导入 EBookManagementPage
import HolidayManagementPage from '../pages/HolidayManagementPage'; // 导入 HolidayManagementPage
import CommunicationPage from '../pages/CommunicationPage';
import PostDetailPage from '../pages/PostDetailPage';
import NewsStatsPage from '../pages/NewsStatsPage';
import NewsManagementPage from '../pages/NewsManagementPage';
import AddCalibrationRecordPage from '../pages/AddCalibrationRecordPage';
import SensorCalibrationHistoryPage from '../pages/SensorCalibrationHistoryPage';
import NewPostPage from '../pages/NewPostPage';
 
 const router = createBrowserRouter([
 {
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: (
          <ProtectedRoute pageName="仪表盘"> {/* 使用 ProtectedRoute 判断登录状态 */}
            <DashboardPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "meeting-rooms",
        element: <ProtectedRoute pagePath="/meeting-rooms" pageName="会议室预定"><MeetingRoomBookingPage /></ProtectedRoute>
      },
      { path: "schedule", element: <GuestRoute><SchedulePage /></GuestRoute> },
      { path: "trial-schedule", element: <GuestRoute><TrialScheduleContainer /></GuestRoute> },
      { path: "shift-schedule", element: <GuestRoute><ShiftScheduleContainer /></GuestRoute> },
      {
        path: "events",
        element: <ProtectedRoute pagePath="/events" pageName="事件管理"><EventsPage /></ProtectedRoute>
      },
      {
        path: "equipment",
        element: <ProtectedRoute pagePath="/equipment" pageName="设备管理"><EquipmentPage /></ProtectedRoute>
      },
      {
        path: "profile",
        element: <ProtectedRoute pagePath="/profile" pageName="个人资料"><ProfilePage /></ProtectedRoute>
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
        element: <ProtectedRoute pagePath="/announcements" pageName="公告"><AnnouncementsPage /></ProtectedRoute>
      },
      {
        path: "intelligent-chat",
        element: <ProtectedRoute pagePath="/intelligent-chat" pageName="智能聊天"><IntelligentChatPage /></ProtectedRoute>
      },
      {
        path: "ragflow-chat",
        element: <ProtectedRoute pagePath="/ragflow-chat" pageName="Ragflow 聊天"><RagflowChatPage /></ProtectedRoute>
      },
      {
        path: "file-analysis",
        element: <ProtectedRoute pagePath="/file-analysis" pageName="文件分析"><FileAnalysisPage /></ProtectedRoute>
      },
      {
        path: "docs/cdepsio6",
        element: <ProtectedRoute pagePath="/docs/cdepsio6" pageName="文档"><DocsPage /></ProtectedRoute>
      },
      {
        path: "books/:bookId/:chapterId/edit", // 新增章节编辑路由
        element: <ProtectedRoute pageName="章节编辑器"><ChapterEditorPage /></ProtectedRoute> // 只有管理员可以访问
      },
      {
        path: "memos", // 新增备忘录路由
        element: <ProtectedRoute pagePath="/memos" pageName="备忘录"><MemoPage /></ProtectedRoute>
      },
      {
        path: "dify-apps",
        element: <ProtectedRoute pagePath="/dify-apps" pageName="Dify 应用列表"><DifyAppList /></ProtectedRoute>
      },
      {
        path: "dify-apps/:appId",
        element: <ProtectedRoute pagePath="/dify-apps/:appId" pageName="Dify 应用查看器"><DifyAppViewer /></ProtectedRoute>
      },
      {
        path: "office-assistant",
        element: <ProtectedRoute pagePath="/office-assistant" pageName="办公室助理"><OfficeAssistant /></ProtectedRoute>
      },
      {
        path: "projects", // Move ProjectsPage to root level
        element: <ProtectedRoute pagePath="/projects" pageName="项目"><ProjectsPage /></ProtectedRoute>
      },
      {
        path: "notifications", // Add NotificationsPage to root level
        element: <ProtectedRoute pagePath="/notifications" pageName="通知"><NotificationsPage /></ProtectedRoute>
      },
      {
        path: "documents", // 将 DocumentsPage 移动到主页面路由
        element: <ProtectedRoute pagePath="/documents" pageName="文档管理"><DocumentsPage /></ProtectedRoute>
      },
      {
        path: "sensor-management", // 新增传感器管理路由
        element: <ProtectedRoute pagePath="/sensor-management" pageName="传感器管理"><SensorManagementPage /></ProtectedRoute>
      },
      {
        path: "sensor-categories", // 新增传感器类别管理路由
        element: <ProtectedRoute pagePath="/sensor-categories" pageName="传感器类别管理"><SensorCategoryManagementPage /></ProtectedRoute>
      },
      {
        path: "storage-locations", // 新增存放位置管理路由
        element: <ProtectedRoute pagePath="/storage-locations" pageName="存储位置管理"><StorageLocationManagementPage /></ProtectedRoute>
      },
      {
        path: "sensor-calibration/:id", // 新增传感器校准管理路由，:id 为动态参数
        element: <ProtectedRoute pagePath="/sensor-calibration/:id" pageName="传感器校准管理"><SensorCalibrationManagementPage /></ProtectedRoute>
      },
      {
        path: "sensors/:id", // 新增传感器详情路由
        element: <ProtectedRoute pagePath="/sensors/:id" pageName="传感器详情"><SensorDetailPage /></ProtectedRoute>
      },
      {
        path: "communication",
        element: <ProtectedRoute pagePath="/communication" pageName="交流"><CommunicationPage /></ProtectedRoute>
      },
      {
        path: "communication/post/:postId",
        element: <ProtectedRoute pagePath="/communication/post/:postId" pageName="帖子详情"><PostDetailPage /></ProtectedRoute>
      },
      {
        path: "communication/new",
        element: <ProtectedRoute pagePath="/communication/new" pageName="新帖子"><NewPostPage /></ProtectedRoute>
      },
      {
        path: "sensor-management/add-record",
        element: <ProtectedRoute pagePath="/sensor-management/add-record" pageName="添加校准记录"><AddCalibrationRecordPage /></ProtectedRoute>
      },
      {
        path: "sensor-management/history/:sensorId",
        element: <ProtectedRoute pagePath="/sensor-management/history/:sensorId" pageName="传感器校准历史"><SensorCalibrationHistoryPage /></ProtectedRoute>
      }
    ]
  },
  {
    path: "/control-panel",
    element: <ProtectedRoute roles={['admin', 'manager']} pageName="管理后台"><AdminLayout /></ProtectedRoute>,
    children: [
      { index: true, element: <Navigate to="trials" replace /> },
      {
        path: "trials",
        element: <ProtectedRoute pagePath="/control-panel/trials" pageName="试验管理"><TrialsPage /></ProtectedRoute>
      },
      {
        path: "personnel",
        element: <ProtectedRoute pagePath="/control-panel/personnel" pageName="人员管理"><PersonnelManagementPage /></ProtectedRoute>
      },
      {
        path: "personnel/:id",
        element: <ProtectedRoute pagePath="/control-panel/personnel/:id" pageName="人员详情"><PersonnelDetailPage /></ProtectedRoute>
      },
      {
        path: "personnel/edit/:id",
        element: <ProtectedRoute pagePath="/control-panel/personnel/edit/:id" pageName="编辑人员"><PersonnelEditPage /></ProtectedRoute>
      },
      {
        path: "schedules",
        element: <ProtectedRoute pagePath="/control-panel/schedules" pageName="排班管理"><ScheduleManagementPage /></ProtectedRoute>
      },
      {
        path: "equipment",
        element: <ProtectedRoute pagePath="/control-panel/equipment" pageName="设备管理 (Admin)"><EquipmentPage /></ProtectedRoute>
      },
      {
        path: "settings",
        element: <ProtectedRoute pagePath="/control-panel/settings" pageName="系统设置"><SystemSettingsPage /></ProtectedRoute>
      },
      {
        path: "announcements",
        element: <ProtectedRoute pagePath="/control-panel/announcements" pageName="管理公告"><ManageAnnouncementsPage /></ProtectedRoute>
      },
      {
        path: "announcements/new",
        element: <ProtectedRoute pagePath="/control-panel/announcements/new" pageName="新公告"><AnnouncementForm /></ProtectedRoute>
      },
      {
        path: "announcements/edit/:id",
        element: <ProtectedRoute pagePath="/control-panel/announcements/edit/:id" pageName="编辑公告"><AnnouncementForm /></ProtectedRoute>
      },
      {
        path: "dify-app-management",
        element: <ProtectedRoute pagePath="/control-panel/dify-app-management" pageName="Dify 应用管理"><DifyAppManagementPage /></ProtectedRoute>
      },
      {
        path: "schedule-settings",
        element: <ProtectedRoute pagePath="/control-panel/schedule-settings" pageName="排班设置"><ScheduleSettingsPage /></ProtectedRoute>
      },
      {
        path: "compliance", // Add CompliancePage route under /control-panel
        element: <ProtectedRoute pagePath="/control-panel/compliance" pageName="合规性"><CompliancePage /></ProtectedRoute>
      },
      {
        path: "meeting-room-management",
        element: <ProtectedRoute pagePath="/control-panel/meeting-room-management" pageName="会议室管理"><MeetingRoomManagementPage /></ProtectedRoute>
      },
      {
        path: "user-management",
        element: <ProtectedRoute pagePath="/control-panel/user-management" pageName="用户管理"><UserManagementPage /></ProtectedRoute>
      },
      {
        path: "ebook-management",
        element: <ProtectedRoute pagePath="/control-panel/ebook-management" pageName="电子书管理"><EBookManagementPage /></ProtectedRoute>
      },
      {
       path: "holidays",
       element: <ProtectedRoute pagePath="/control-panel/holidays" pageName="假期管理"><HolidayManagementPage /></ProtectedRoute>
      },
      {
        path: "news-stats",
        element: <ProtectedRoute pagePath="/control-panel/news-stats" pageName="新闻统计"><NewsStatsPage /></ProtectedRoute>
      },
      {
        path: "news-management",
        element: <ProtectedRoute pagePath="/control-panel/news-management" pageName="新闻管理"><NewsManagementPage /></ProtectedRoute>
      },
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

