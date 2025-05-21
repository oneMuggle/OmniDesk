import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import './styles/TrialCalendar.css';
import { fromServerFormat } from '../../utils/dateUtils';
import { getStatusConfig, getTrialColor } from '../../utils/calendarUtils';
import BaseCalendar from './BaseCalendar';

const TrialCalendar = ({
  trials,
  defaultEvents,
  isGuest,
  onTrialDateClick,
  onTrialEventClick,
  onTrialSelect = () => {}
}) => {
  const events = useMemo(() => {
    const trialEvents = (Array.isArray(trials) ? trials : []).flatMap(trial =>
      (Array.isArray(trial?.time_slots) ? trial.time_slots : []).map((slot, index) => ({
        id: `trial-${trial.id}-${index}`,
        title: `${trial.title}`,
        start: fromServerFormat(slot.start_time)?.toDate(),
        end: fromServerFormat(slot.end_time)?.toDate(),
        extendedProps: {
          type: 'TRIAL',
          status: trial.status,
          client: trial.client,
          equipment: trial.equipment,
          personnel: trial.responsible_persons,
          description: trial.description,
          trialId: trial.id
        },
        color: getTrialColor(trial.id),
        borderColor: getStatusConfig(trial.status).color,
        allDay: false,
        editable: false,
        tooltip: {
          title: `${trial.title}`,
          description: `
            状态: ${getStatusConfig(trial.status).text}
            负责人: ${trial.responsible_persons?.join(', ') || '无'}
            设备: ${trial.equipment || '无'}
            描述: ${trial.description || '无'}
          `
        }
      }))
    );
    return [...defaultEvents, ...trialEvents];
  }, [trials, defaultEvents]);

  return (
    <BaseCalendar
      events={events}
      onDateClick={onTrialDateClick}
      onEventClick={onTrialEventClick}
      editable={!isGuest}
      selectable={!isGuest}
      select={onTrialSelect}
    />
  );
};

TrialCalendar.propTypes = {
  trials: PropTypes.array,
  defaultEvents: PropTypes.array,
  isGuest: PropTypes.bool,
  onTrialDateClick: PropTypes.func,
  onTrialEventClick: PropTypes.func,
  onTrialSelect: PropTypes.func
};

export default TrialCalendar;
