import { createBrowserRouter, Navigate } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import PropTypes from 'prop-types';
import ProtectedRoute from '../features/auth/components/ProtectedRoute';
import GuestRoute from '../features/auth/components/GuestRoute';
import App from '../App';
import AdminAppWrapper from '../AdminAppWrapper';

// Lazy load all page components for code splitting
const DashboardPage = lazy(() => import('../shared/pages/DashboardPage'));
const SchedulePage = lazy(() => import('../features/schedule/pages/SchedulePage'));
const SystemSettingsPage = lazy(() => import('../shared/pages/SystemSettingsPage'));
const IntelligentChatPage = lazy(() => import('../shared/pages/IntelligentChatPage'));
const RagflowChatPage = lazy(() => import('../shared/pages/RagflowChatPage'));
const EventsPage = lazy(() => import('../shared/pages/EventsPage'));
const AdminLayout = lazy(() => import('../features/admin/components/AdminLayout'));
const ProfilePage = lazy(() => import('../features/profile/pages/ProfilePage'));
const PersonnelDetailPage = lazy(() => import('../features/personnel/pages/PersonnelDetailPage'));
const Login = lazy(() => import('../features/auth/pages/Login'));
const Register = lazy(() => import('../features/auth/pages/Register'));
const DocumentsPage = lazy(() => import('../features/documents/pages/DocumentsPage'));
const AnnouncementsPage = lazy(() => import('../features/announcements/pages/AnnouncementsPage'));
const EquipmentPage = lazy(() => import('../features/equipment/pages/EquipmentPage'));
const FileAnalysisPage = lazy(() => import('../shared/pages/FileAnalysisPage'));
const DocsPage = lazy(() => import('../shared/pages/DocsPage'));
const BookPage = lazy(() => import('../shared/pages/BookPage'));
const BookReaderPage = lazy(() => import('../shared/pages/BookReaderPage'));
const LibraryPage = lazy(() => import('../shared/pages/LibraryPage'));
const ChapterEditorPage = lazy(() => import('../shared/pages/ChapterEditorPage'));
const TrialsPage = lazy(() => import('../shared/pages/TrialsPage'));
const PersonnelManagementPage = lazy(() => import('../features/personnel/pages/PersonnelManagementPage'));
const PersonnelEditPage = lazy(() => import('../features/personnel/pages/PersonnelEditPage'));
const TrialScheduleContainer = lazy(() => import('../features/schedule/components/TrialScheduleContainer'));
const ShiftScheduleContainer = lazy(() => import('../features/schedule/components/ShiftScheduleContainer'));
const MemoPage = lazy(() => import('../features/memo/pages/MemoPage'));
const ManageAnnouncementsPage = lazy(() => import('../features/announcements/pages/ManageAnnouncementsPage'));
const AnnouncementForm = lazy(() => import('../features/announcements/components/AnnouncementForm'));
const DifyAppList = lazy(() => import('../features/dify-apps/pages/DifyAppList'));
const DifyAppViewer = lazy(() => import('../features/dify-apps/pages/DifyAppViewer'));
const DifyAppManagementPage = lazy(() => import('../features/dify-apps/pages/DifyAppManagementPage'));
const ScheduleManagementPage = lazy(() => import('../features/schedule/pages/ScheduleManagementPage'));
const ScheduleSettingsPage = lazy(() => import('../features/schedule/pages/ScheduleSettingsPage'));
const OfficeAssistant = lazy(() => import('../features/office-assistant/pages/OfficeAssistant'));
const ProjectsPage = lazy(() => import('../features/projects/pages/ProjectsPage'));
const MeetingRoomBookingPage = lazy(() => import('../features/meeting-room/pages/MeetingRoomBookingPage.jsx'));
const MeetingRoomManagementPage = lazy(() => import('../features/meeting-room/pages/MeetingRoomManagementPage'));
const UserManagementPage = lazy(() => import('../features/user/pages/UserManagementPage'));
const SensorManagementPage = lazy(() => import('../features/sensor/pages/SensorManagementPage'));
const SensorListPage = lazy(() => import('../features/sensor/pages/SensorListPage'));
const SensorCategoryManagementPage = lazy(() => import('../features/sensor/pages/SensorCategoryManagementPage.jsx'));
const SensorArchiveLocationManagementPage = lazy(() => import('../features/sensor/pages/SensorArchiveLocationManagementPage.jsx'));
const SensorCalibrationManagementPage = lazy(() => import('../features/sensor/pages/SensorCalibrationManagementPage'));
const SensorDetailPage = lazy(() => import('../features/sensor/pages/SensorDetailPage'));
const EBookManagementPage = lazy(() => import('../features/ebook/pages/EBookManagementPage'));
const HolidayManagementPage = lazy(() => import('../features/schedule/pages/HolidayManagementPage'));
const CommunicationPage = lazy(() => import('../features/communication/pages/CommunicationPage'));
const PostDetailPage = lazy(() => import('../shared/pages/PostDetailPage'));
const NewsStatsPage = lazy(() => import('../features/news/pages/NewsStatsPage'));
const NewsManagementPage = lazy(() => import('../features/news/pages/NewsManagementPage'));
const AddCalibrationRecordPage = lazy(() => import('../features/sensor/pages/AddCalibrationRecordPage'));
const SensorCalibrationHistoryPage = lazy(() => import('../features/sensor/pages/SensorCalibrationHistoryPage'));
const NewPostPage = lazy(() => import('../features/communication/pages/NewPostPage'));

const LoadingFallback = () => (
  <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '200px' }}>
    加载中...
  </div>
);

const LazyComponent = ({ component: Component, ...props }) => (
  <Suspense fallback={<LoadingFallback />}>
    <Component {...props} />
  </Suspense>
);

LazyComponent.propTypes = {
  component: PropTypes.elementType.isRequired,
};

const UnauthorizedPage = lazy(() => import('../features/auth/pages/UnauthorizedPage'));

const router = createBrowserRouter([
  // 认证相关路由 - 不使用 App 布局（无侧边栏）
  {
    path: "/login",
    element: <GuestRoute><LazyComponent component={Login} /></GuestRoute>
  },
  {
    path: "/register",
    element: <GuestRoute><LazyComponent component={Register} /></GuestRoute>
  },
  {
    path: "/unauthorized",
    element: <LazyComponent component={UnauthorizedPage} />
  },
  // 管理中心路由 - 使用独立 AdminAppWrapper 布局（无主侧边栏，全屏显示）
  {
    path: "/control-panel",
    element: (
      <ProtectedRoute pageName="控制面板"><AdminAppWrapper /></ProtectedRoute>
    ),
    children: [
      {
        element: <AdminLayout />,
        children: [
          {
            index: true,
            element: <Navigate to="personnel" replace />
          },
          {
            path: "personnel",
            element: <LazyComponent component={PersonnelManagementPage} />
          },
          {
            path: "personnel/add",
            element: <LazyComponent component={PersonnelEditPage} />
          },
          {
            path: "personnel/:personnelId",
            element: <LazyComponent component={PersonnelDetailPage} />
          },
          {
            path: "personnel/:personnelId/edit",
            element: <LazyComponent component={PersonnelEditPage} />
          },
          {
            path: "documents",
            element: <LazyComponent component={DocumentsPage} />
          },
          {
            path: "announcements/manage",
            element: <LazyComponent component={ManageAnnouncementsPage} />
          },
          {
            path: "announcements/create",
            element: <LazyComponent component={AnnouncementForm} />
          },
          {
            path: "announcements/:announcementId/edit",
            element: <LazyComponent component={AnnouncementForm} />
          },
          {
            path: "dify-apps",
            element: <LazyComponent component={DifyAppManagementPage} />
          },
          {
            path: "schedule",
            element: <LazyComponent component={ScheduleManagementPage} />
          },
          {
            path: "schedule/settings",
            element: <LazyComponent component={ScheduleSettingsPage} />
          },
          {
            path: "schedule/holiday",
            element: <LazyComponent component={HolidayManagementPage} />
          },
          {
            path: "projects",
            element: <LazyComponent component={ProjectsPage} />
          },
          {
            path: "meeting-rooms",
            element: <LazyComponent component={MeetingRoomManagementPage} />
          },
          {
            path: "users",
            element: <LazyComponent component={UserManagementPage} />
          },
          {
            path: "sensors",
            element: <LazyComponent component={SensorManagementPage} />
          },
          {
            path: "sensors/list",
            element: <LazyComponent component={SensorListPage} />
          },
          {
            path: "sensors/categories",
            element: <LazyComponent component={SensorCategoryManagementPage} />
          },
          {
            path: "sensors/archive-locations",
            element: <LazyComponent component={SensorArchiveLocationManagementPage} />
          },
          {
            path: "sensors/calibration",
            element: <LazyComponent component={SensorCalibrationManagementPage} />
          },
          {
            path: "sensors/:sensorId",
            element: <LazyComponent component={SensorDetailPage} />
          },
          {
            path: "sensors/:sensorId/calibration/add",
            element: <LazyComponent component={AddCalibrationRecordPage} />
          },
          {
            path: "sensors/:sensorId/calibration/history",
            element: <LazyComponent component={SensorCalibrationHistoryPage} />
          },
          {
            path: "ebooks",
            element: <LazyComponent component={EBookManagementPage} />
          },
          {
            path: "news",
            element: <LazyComponent component={NewsManagementPage} />
          },
          {
            path: "news/stats",
            element: <LazyComponent component={NewsStatsPage} />
          }
        ]
      }
    ]
  },
  // 主应用路由 - 使用 App 布局（含侧边栏）
  {
    path: "/",
    element: <App />,
    children: [
      {
        index: true,
        element: (
          <ProtectedRoute pageName="仪表盘">
            <LazyComponent component={DashboardPage} />
          </ProtectedRoute>
        ),
      },
      {
        path: "meeting-rooms",
        element: <ProtectedRoute pageName="会议室预定"><LazyComponent component={MeetingRoomBookingPage} /></ProtectedRoute>
      },
      { path: "schedule", element: <GuestRoute><LazyComponent component={SchedulePage} /></GuestRoute> },
      { path: "trial-schedule", element: <GuestRoute><LazyComponent component={TrialScheduleContainer} /></GuestRoute> },
      { path: "shift-schedule", element: <GuestRoute><LazyComponent component={ShiftScheduleContainer} /></GuestRoute> },
      {
        path: "events",
        element: <ProtectedRoute pagePath="/events" pageName="事件管理"><LazyComponent component={EventsPage} /></ProtectedRoute>
      },
      {
        path: "equipment",
        element: <ProtectedRoute pagePath="/equipment" pageName="设备管理"><LazyComponent component={EquipmentPage} /></ProtectedRoute>
      },
      {
        path: "profile",
        element: <ProtectedRoute pagePath="/profile" pageName="个人资料"><LazyComponent component={ProfilePage} /></ProtectedRoute>
      },
      {
        path: "library",
        element: <LazyComponent component={LibraryPage} />
      },
      {
        path: "books/:bookId",
        element: <BookPage />
      },
      {
        path: "books/:bookId/reader",
        element: <BookReaderPage />
      },
      {
        path: "books/:bookId/editor",
        element: <ChapterEditorPage />
      },
      {
        path: "intelligent-chat",
        element: <ProtectedRoute pageName="智能问答"><LazyComponent component={IntelligentChatPage} /></ProtectedRoute>
      },
      {
        path: "ragflow-chat",
        element: <ProtectedRoute pageName="Ragflow聊天"><LazyComponent component={RagflowChatPage} /></ProtectedRoute>
      },
      {
        path: "dify-apps",
        element: <ProtectedRoute pageName="Dify应用"><LazyComponent component={DifyAppList} /></ProtectedRoute>
      },
      {
        path: "dify-apps/:appId",
        element: <ProtectedRoute pageName="Dify应用"><LazyComponent component={DifyAppViewer} /></ProtectedRoute>
      },
      {
        path: "office-assistant",
        element: <ProtectedRoute pageName="Office助手"><LazyComponent component={OfficeAssistant} /></ProtectedRoute>
      },
      {
        path: "file-analysis",
        element: <ProtectedRoute pageName="文件分析"><LazyComponent component={FileAnalysisPage} /></ProtectedRoute>
      },
      {
        path: "memos",
        element: <ProtectedRoute pageName="备忘录"><LazyComponent component={MemoPage} /></ProtectedRoute>
      },
      {
        path: "communication",
        element: <ProtectedRoute pageName="交流"><LazyComponent component={CommunicationPage} /></ProtectedRoute>
      },
      {
        path: "communication/new",
        element: <ProtectedRoute pageName="新建帖子"><LazyComponent component={NewPostPage} /></ProtectedRoute>
      },
      {
        path: "communication/:postId",
        element: <LazyComponent component={PostDetailPage} />
      },
      {
        path: "announcements",
        element: <LazyComponent component={AnnouncementsPage} />
      },
      {
        path: "system-settings",
        element: <ProtectedRoute pageName="系统设置"><LazyComponent component={SystemSettingsPage} /></ProtectedRoute>
      },
      {
        path: "trials",
        element: <ProtectedRoute pageName="试验管理"><LazyComponent component={TrialsPage} /></ProtectedRoute>
      },
      {
        path: "docs/:docId",
        element: <DocsPage />
      },
      {
        path: "*",
        element: <Navigate to="/" replace />
      }
    ]
  }
]);

export default router;