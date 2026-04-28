import { Tabs } from 'antd';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

const SensorManagementPage = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const getActiveKey = () => {
    const path = location.pathname.split('/').pop();
    if (path === 'categories') return 'categories';
    if (path === 'archive-locations' || path === 'storage-locations') return 'storage-locations';
    return 'list';
  };

  const handleTabChange = (key) => {
    switch (key) {
      case 'list':
        navigate('/control-panel/sensors/list');
        break;
      case 'categories':
        navigate('/control-panel/sensors/categories');
        break;
      case 'storage-locations':
        navigate('/control-panel/sensors/archive-locations');
        break;
      default:
        break;
    }
  };

  const items = [
    {
      key: 'list',
      label: '传感器列表',
    },
    {
      key: 'categories',
      label: '传感器类别',
    },
    {
      key: 'storage-locations',
      label: '存档位置',
    },
  ];

  return (
    <div>
      <h1>传感器管理</h1>
      <Tabs activeKey={getActiveKey()} onChange={handleTabChange} items={items} />
      <div style={{ padding: '20px' }}>
        <Outlet />
      </div>
    </div>
  );
};

export default SensorManagementPage;