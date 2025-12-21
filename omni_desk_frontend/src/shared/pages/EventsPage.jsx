import { useState } from 'react';
import { useAuth } from '../../features/auth/context/AuthContext';

const EventsPage = () => {
  const { user } = useAuth();
  const [events, setEvents] = useState([]);
  const [newEventTitle, setNewEventTitle] = useState('');

  const canManageEvents = user?.role === 'admin' || user?.role === 'manager';

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
      <ul>
        {events.map(event => (
          <li key={event.id}>{event.title}</li>
        ))}
      </ul>
    </div>
  );
};

export default EventsPage;
