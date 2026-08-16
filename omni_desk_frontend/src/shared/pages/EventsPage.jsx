import { useEffect, useState } from 'react';
import { useAuth } from '../../features/auth/context/AuthContext';
import apiClient from '../api/apiClient';

const EventsPage = () => {
  const { hasPermission } = useAuth();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newEventTitle, setNewEventTitle] = useState('');

  // R4-B5: 权限判断收敛到 hasPermission(与导航守卫同源,超管恒 true)
  const canManageEvents = hasPermission(['admin', 'manager']);

  // 实接后端 API: GET /api/events/
  // 响应可能是分页结构 {results: [...]} 或纯数组,统一归一化
  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const response = await apiClient.get('events/');
        const data = response.data;
        setEvents(Array.isArray(data) ? data : (data?.results ?? []));
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };
    fetchEvents();
  }, []);

  const handleInputChange = (e) => {
    setNewEventTitle(e.target.value);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (newEventTitle.trim() && canManageEvents) {
      setEvents(prevEvents => [...prevEvents, {
        id: Date.now(),
        title: newEventTitle
      }]);
      setNewEventTitle('');
    }
  };

  return (
    <div className="events-page">
      <h2>事件管理</h2>
      {canManageEvents && (
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={newEventTitle}
            onChange={handleInputChange}
            placeholder="输入新事件"
          />
          <button type="submit">添加事件</button>
        </form>
      )}
      {loading && <p>加载中...</p>}
      {error && <p className="error-message">加载失败: {error}</p>}
      <ul>
        {events.map(event => (
          <li key={event.id ?? event.title}>
            {event.title || event.name || String(event.id)}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default EventsPage;
