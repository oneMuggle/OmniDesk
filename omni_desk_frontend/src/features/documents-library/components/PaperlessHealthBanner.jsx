import { Alert } from 'antd';
import { usePaperlessHealth } from '../hooks/usePaperlessHealth';

export default function PaperlessHealthBanner() {
  const { isHealthy, loading } = usePaperlessHealth();
  if (loading || isHealthy) return null;
  return (
    <Alert
      type="warning"
      showIcon
      message="paperless 文档服务暂不可用"
      description="新上传的文档将稍后自动同步,搜索暂不包含 paperless 文档。"
      style={{ margin: '8px 0' }}
    />
  );
}
