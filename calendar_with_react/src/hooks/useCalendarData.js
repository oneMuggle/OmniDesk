import { useState, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { calendarApi } from '../api/calendar';
import { getTrials } from '../api/trials';
import { fromServerFormat } from '../utils/dateUtils';

export const useCalendarData = () => {
  const queryClient = useQueryClient();
  const [defaultEvents, setDefaultEvents] = useState([]);
  const [darkMode, setDarkMode] = useState(false);
  const [calendarType, setCalendarType] = useState('trial');
  const [currentEvent, setCurrentEvent] = useState(null);
  const [selectedTrial, setSelectedTrial] = useState(null);

  const { data: trials = [], isLoading: isTrialsLoading } = useQuery({
    queryKey: ['trials'],
    queryFn: () => getTrials().then(res => Array.isArray(res?.results) ? res.results : []),
    gcTime: 600000,
    staleTime: 300000
  });

  const { data: schedules = [], isLoading: isSchedulesLoading } = useQuery({
    queryKey: ['schedules'],
    queryFn: async () => {
      try {
        const response = await calendarApi.getSchedules();
        return Array.isArray(response) ? response : [];
      } catch (error) {
        console.error('获取排班数据失败:', error);
        return [];
      }
    },
    gcTime: 600000,
    staleTime: 300000
  });

  const { data: personnel = [], isLoading: isPersonnelLoading } = useQuery({
    queryKey: ['personnel'],
    queryFn: () => calendarApi.getPersonnel(),
    gcTime: 600000,
    staleTime: 300000
  });

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        if (!selectedTrial) {
          console.warn('未选择试验，跳过加载时间槽');
          return;
        }
        
        const response = await calendarApi.fetchTimeSlotsByTrial(selectedTrial.id);
        const events = response.map(slot => ({
          id: slot.id,
          title: slot.description || '时间槽',
          start: new Date(slot.start),
          end: new Date(slot.end),
          extendedProps: {
            trialId: slot.trialId
          }
        }));
        setDefaultEvents(events);
      } catch (error) {
        console.error('加载试验日历失败:', error);
      }
    };

    document.body.classList.toggle('dark-mode', darkMode);
    fetchEvents();
  }, [darkMode, selectedTrial]);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
  };

  return {
    trials,
    isTrialsLoading,
    schedules,
    isSchedulesLoading,
    personnel,
    isPersonnelLoading,
    defaultEvents,
    setDefaultEvents,
    darkMode,
    setDarkMode,
    toggleDarkMode,
    calendarType,
    setCalendarType,
    currentEvent,
    setCurrentEvent,
    selectedTrial,
    setSelectedTrial,
    queryClient
  };
};
