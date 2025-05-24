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
    const fetchAllEvents = async () => {
      try {
        if (trials.length === 0) return;
        
        // 批量获取所有试验的时间槽
        console.log('开始获取试验数据，试验数量:', trials.length);
        const allSlots = await Promise.all(
          trials.map(trial => {
            console.log(`获取试验 ${trial.id} 的时间槽`);
            return calendarApi.fetchTimeSlotsByTrial(trial.id)
              .then(slots => {
                console.log(`试验 ${trial.id} 获取到 ${slots.length} 个时间槽`);
                return slots.map(slot => ({
                  ...slot,
                  trialTitle: trial.title,
                  trialStatus: trial.status
                }));
              })
              .catch(error => {
                console.error(`获取试验 ${trial.id} 时间槽失败:`, error);
                return [];
              });
          })
        );
        
        const flattenedSlots = allSlots.flat();
        console.log('扁平化后的时间槽数据:', flattenedSlots);
        
        const events = flattenedSlots.flatMap(slot => {
          try {
            const start = fromServerFormat(slot.start_time || slot.start)?.toDate();
            const end = fromServerFormat(slot.end_time || slot.end)?.toDate();
            
            if (!start || !end || isNaN(start.getTime()) || isNaN(end.getTime())) {
              console.error(`无效的时间槽数据 ${slot.id}:`, slot);
              return [];
            }

            console.log(`处理时间槽 ${slot.id}:`, {
              start: start.toString(),
              end: end.toString(),
              isValid: true
            });
            
            return [{
              id: slot.id,
              title: slot.trialTitle || '试验时间槽',
              start: start,
              end: end,
              extendedProps: {
                trialId: slot.trial,
                status: slot.trialStatus,
                description: slot.description
              }
            }];
          } catch (error) {
            console.error(`处理时间槽 ${slot.id} 失败:`, error);
            return [];
          }
        });
        
        console.log('生成的事件对象:', events);
        
        setDefaultEvents(events);
      } catch (error) {
        console.error('加载时间槽失败:', error);
      }
    };

    document.body.classList.toggle('dark-mode', darkMode);
    fetchAllEvents();
  }, [darkMode, trials]);

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
