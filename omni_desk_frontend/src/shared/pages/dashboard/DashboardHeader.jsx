import { Typography } from 'antd';
import PropTypes from 'prop-types';

const { Title, Text } = Typography;

const DashboardHeader = () => {
  return (
    <div className="dashboard-header">
      <Title level={2} className="dashboard-title">欢迎来到智能办公桌面管理系统</Title>
      <Text type="secondary">这里是您的智能办公中心，高效管理您的日常工作。</Text>
    </div>
  );
};

DashboardHeader.propTypes = {};

export default DashboardHeader;
