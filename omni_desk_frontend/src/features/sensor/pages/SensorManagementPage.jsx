import React from 'react';
import { Link } from 'react-router-dom';
import { Button } from 'antd';

const SensorManagementPage = () => {
  return (
    <div>
      <h1>传感器管理</h1>
      <p>请选择要管理的项目：</p>
      <div style={{ display: 'flex', gap: '16px' }}>
        <Link to="/control-panel/sensor/category">
          <Button type="primary">管理传感器类别</Button>
        </Link>
        <Link to="/control-panel/sensor/storage-location">
          <Button type="primary">管理存放地点</Button>
        </Link>
      </div>
    </div>
  );
};

export default SensorManagementPage;