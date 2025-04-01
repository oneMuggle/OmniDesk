import axios from 'axios';

// 创建专属日历API实例
const calendarClient = axios.create({
  baseURL: process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json'
  }
});

export const calendarApi = {
  // 获取试验日历事件
  fetchTrialEvents: async () => {
    try {
      const response = await calendarClient.get('/events/trails/');
      return response.data.map(trial => ({
        id: trial.id,
        title: trial.title,
        start: new Date(trial.start_date),
        end: new Date(trial.end_date),
        extendedProps: {
          equipment: trial.equipment,
          personnel: trial.responsible_persons
        }
      }));
    } catch (error) {
      console.error('Failed to fetch trial events:', error);
      return [];
    }
  },

  // 保留原有事件接口（可选）
  fetchCalendarEvents: () => calendarClient.get('/events/'),
  createCalendarEvent: (eventData) => calendarClient.post('/events/', eventData),
  updateCalendarEvent: (id, eventData) => calendarClient.put(`/events/${id}/`, eventData),
  deleteCalendarEvent: (id) => calendarClient.delete(`/events/${id}/`)
};
