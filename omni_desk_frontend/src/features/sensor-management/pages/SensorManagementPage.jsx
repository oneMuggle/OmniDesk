import SensorCategory from '../components/SensorCategory';
import StorageLocation from '../components/StorageLocation';
import { Divider } from 'antd';

const SensorManagementPage = () => {
  return (
    <div>
      <h1>传感器管理</h1>
      <h2>传感器类别</h2>
      <SensorCategory />
      <Divider />
      <h2>存放地点</h2>
      <StorageLocation />
    </div>
  );
};

export default SensorManagementPage;