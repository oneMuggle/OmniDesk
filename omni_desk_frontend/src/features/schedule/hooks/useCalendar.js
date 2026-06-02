import { useState } from 'react';
import dayjs from 'dayjs';

export const useCalendar = (initialDate = dayjs()) => {
  const [selectedDate, setSelectedDate] = useState(initialDate);

  const handleSelectDate = (date) => {
    setSelectedDate(date);
  };

  return {
    selectedDate,
    handleSelectDate,
  };
};
