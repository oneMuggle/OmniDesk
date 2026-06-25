import { Switch, Space, message } from 'antd';
import { useDemoMode } from '../context/DemoContext';
import { setDemoModeEnabled } from '../api/axiosConfig';

/**
 * 演示模式开关组件
 * 使用 Ant Design Switch，切换时同步 DemoContext 和 axios 拦截器
 */
const DemoToggle = () => {
  const { isDemoMode, setDemoMode } = useDemoMode();

  const handleChange = (checked) => {
    setDemoMode(checked);
    setDemoModeEnabled(checked);
    message.success(checked ? '已切换到演示模式' : '已切换到真实模式');
  };

  return (
    <Space>
      <span style={{ fontSize: 12, color: '#666' }}>演示模式</span>
      <Switch
        size="small"
        checked={isDemoMode}
        onChange={handleChange}
      />
    </Space>
  );
};

export default DemoToggle;
