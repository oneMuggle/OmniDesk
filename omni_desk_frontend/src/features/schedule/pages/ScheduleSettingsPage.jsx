import React from 'react';
import SequenceManager from '../../../shared/components/SequenceManager';

const ScheduleSettingsPage = () => {
  return (
    <div>
      <h1>排班设置</h1>
      <p>在这里管理您的排班顺序。</p>
      <hr />
      <SequenceManager />
    </div>
  );
};

export default ScheduleSettingsPage;