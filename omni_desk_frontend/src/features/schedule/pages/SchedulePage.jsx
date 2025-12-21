import PropTypes from 'prop-types';
import ScheduleControls from '../components/ScheduleControls';
import TrialScheduleContainer from '../components/TrialScheduleContainer';
import ShiftScheduleContainer from '../components/ShiftScheduleContainer';
import '../../../shared/components/CalendarPage.css';

const SchedulePage = ({ scheduleType }) => {
  return (
    <div className="schedule-page">
      <div className="schedule-container">
        <ScheduleControls />
        {scheduleType === 'trial' && <TrialScheduleContainer />}
        {scheduleType === 'shift' && <ShiftScheduleContainer />}
      </div>
    </div>
  );
};

SchedulePage.propTypes = {
  scheduleType: PropTypes.string.isRequired,
};

export default SchedulePage;