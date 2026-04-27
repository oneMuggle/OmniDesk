import PropTypes from 'prop-types';
import TrialScheduleContainer from '../components/TrialScheduleContainer';
import ShiftScheduleContainer from '../components/ShiftScheduleContainer';
import '../../../shared/components/CalendarPage.css';

const SchedulePage = ({ scheduleType = 'shift' }) => {
  return (
    <div className="schedule-page">
      <div className="schedule-container">
        {scheduleType === 'trial' && <TrialScheduleContainer />}
        {scheduleType === 'shift' && <ShiftScheduleContainer />}
      </div>
    </div>
  );
};

SchedulePage.propTypes = {
  scheduleType: PropTypes.string,
};

export default SchedulePage;