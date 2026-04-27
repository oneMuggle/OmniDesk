import PropTypes from 'prop-types';
import { UserOutlined } from '@ant-design/icons';
import '../../../shared/components/styles/WeeklyLeaderDisplay.css';

const WeeklyLeaderDisplay = ({ leaders }) => {
  if (!leaders || leaders.length === 0) {
    return null;
  }

  return (
    <div className="weekly-leader-banner">
      <div className="weekly-leader-banner__icon">
        <UserOutlined />
      </div>
      <div className="weekly-leader-banner__content">
        <span className="weekly-leader-banner__label">本周值班领导</span>
        <span className="weekly-leader-banner__names">
          {leaders.map(leader => leader.name).join(' / ')}
        </span>
      </div>
    </div>
  );
};

WeeklyLeaderDisplay.propTypes = {
  leaders: PropTypes.arrayOf(PropTypes.shape({
    name: PropTypes.string.isRequired,
  })).isRequired,
};

export default WeeklyLeaderDisplay;