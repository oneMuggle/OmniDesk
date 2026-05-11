import { useEffect, useState } from 'react';
import { Card, Descriptions, Spin, Tag } from 'antd';
import axios from 'axios';

/**
 * Version info display component.
 * Shows app version, build time, and Django version from /api/system/version/.
 */
function VersionInfo() {
  const [versionData, setVersionData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get('/api/system/version/')
      .then(res => {
        setVersionData(res.data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return <Spin />;
  }

  if (!versionData) {
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
