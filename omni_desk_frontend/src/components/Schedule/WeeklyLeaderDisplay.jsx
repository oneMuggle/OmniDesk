import React from 'react';
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

export default WeeklyLeaderDisplay;