import { useState } from 'react';
import moment from 'moment';

export const useCalendar = (initialDate = moment()) => {
  const [selectedDate, setSelectedDate] = useState(initialDate);

  const handleSelectDate = (date) => {
    setSelectedDate(date);
  };

  return {
    selectedDate,
    handleSelectDate,
  };
};
