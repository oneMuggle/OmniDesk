import { createBrowserRouter } from 'react-router-dom';
import App from '../App';
import Home from '../components/HelloWorld';
import CalendarPage from '../components/CalendarPage';
import Login from '../components/Login';
import ProtectedRoute from '../components/ProtectedRoute';

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      {
        path: '/',
        element: <Home />
      },
      {
        path: '/login',
        element: <Login />
      },
      {
        path: '/calendar',
        element: <ProtectedRoute><CalendarPage /></ProtectedRoute>
      },
      {
        path: '/settings',
        element: <ProtectedRoute><div>设置页面</div></ProtectedRoute>
      },
      {
        path: '/events',
        element: <ProtectedRoute><div>事件页面</div></ProtectedRoute>
      },
      {
        path: '/notifications',
        element: <ProtectedRoute><div>通知页面</div></ProtectedRoute>
      },
      {
        path: '/profile',
        element: <ProtectedRoute><div>个人资料页面</div></ProtectedRoute>
      }
    ]
  }
]);

export default router;
