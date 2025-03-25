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
  // 获取日历事件
  fetchCalendarEvents: () => calendarClient.get('/events/'),
  
  // 创建新事件
  createCalendarEvent: (eventData) => calendarClient.post('/events/', eventData),
  
  // 更新事件
  updateCalendarEvent: (id, eventData) => calendarClient.put(`/events/${id}/`, eventData),
  
  // 删除事件
  deleteCalendarEvent: (id) => calendarClient.delete(`/events/${id}/`)
};
