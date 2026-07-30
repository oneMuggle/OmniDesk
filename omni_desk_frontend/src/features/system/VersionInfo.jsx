import { Card, Descriptions, Spin, Tag } from 'antd';
import { useQuery } from '@tanstack/react-query';
import axiosInstance from '../../shared/api/axiosConfig';

/**
 * Version info display component.
 * Shows app version, build time, and Django version from /api/system/version/.
 */
const fetchSystemVersion = async () => {
  const { data } = await axiosInstance.get('system/version/');
  return data;
};

function VersionInfo() {
  const { data: versionData, isLoading, isError } = useQuery({
    queryKey: ['system-version'],
    queryFn: fetchSystemVersion,
  });

  if (isLoading) {
    return <Spin />;
  }

  if (isError || !versionData) {
    return <div>Unable to load version information.</div>;
  }

  const isDev = versionData.version.includes('dev');

  return (
    <Card title="System Version">
      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="App Version">
          {versionData.version}
          {isDev && <Tag color="orange" style={{ marginLeft: 8 }}>DEV</Tag>}
        </Descriptions.Item>
        <Descriptions.Item label="Build Time">{versionData.build_time}</Descriptions.Item>
        <Descriptions.Item label="Django Version">{versionData.django_version}</Descriptions.Item>
      </Descriptions>
    </Card>
  );
}

export default VersionInfo;
