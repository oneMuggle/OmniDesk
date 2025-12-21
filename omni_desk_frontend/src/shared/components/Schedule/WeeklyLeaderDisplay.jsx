import PropTypes from 'prop-types';
import { Card } from 'antd';

const WeeklyLeaderDisplay = ({ leaders }) => {
  if (!leaders || leaders.length === 0) {
    return null;
  }

  return (
    <Card size="small" style={{ marginBottom: '16px', textAlign: 'center' }}>
      <strong>本周值班领导:</strong> {leaders.map(leader => leader.name).join(', ')}
    </Card>
  );
};

WeeklyLeaderDisplay.propTypes = {
  leaders: PropTypes.arrayOf(PropTypes.shape({
    name: PropTypes.string.isRequired,
  })).isRequired,
};

export default WeeklyLeaderDisplay;