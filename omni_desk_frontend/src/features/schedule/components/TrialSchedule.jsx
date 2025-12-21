import PropTypes from 'prop-types';
import BaseSchedule from './BaseSchedule';

const TrialSchedule = ({
  trialEvents = [],
  isGuest,
  onDateClick,
  onEventClick,
  select = () => {}
}) => {
  return (
    <BaseSchedule
      events={trialEvents}
      onDateClick={onDateClick}
      onEventClick={(clickInfo) => {
        console.log('TrialSchedule - onEventClick:', clickInfo);
        onEventClick(clickInfo);
      }}
      editable={!isGuest}
      selectable={!isGuest}
      select={select}
      slotMinTime="08:00:00"
      slotMaxTime="22:00:00"
    />
  );
};

TrialSchedule.propTypes = {
  trialEvents: PropTypes.arrayOf(
    PropTypes.shape({
      extendedProps: PropTypes.shape({
        type: PropTypes.oneOf(['TRIAL'])
      })
    })
  ),
  isGuest: PropTypes.bool,
  onDateClick: PropTypes.func,
  onEventClick: PropTypes.func,
  select: PropTypes.func
};

export default TrialSchedule;
