import { useState, useEffect } from 'react';
import { Modal, Spin, Alert } from 'antd';
import { getEmbedUrl } from '../api/integrationApi';

const IntegrationIframeViewer = ({ service, open, onClose }) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [embedUrl, setEmbedUrl] = useState(null);

  useEffect(() => {
    if (!service || !open) return;
    const load = async () => {
      try {
        setLoading(true);
        const result = await getEmbedUrl(service.slug);
        setEmbedUrl(result.embed_url);
        setError(null);
      } catch {
        setError('加载嵌入内容失败');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [service, open]);

  return (
    <Modal
      title={service?.name || '集成服务'}
      open={open}
      onCancel={onClose}
      footer={null}
      width="80%"
      style={{ top: 20 }}
    >
      {loading && <Spin size="large" style={{ display: 'block', margin: '40px auto' }} />}
      {error && <Alert message={error} type="error" style={{ marginBottom: 16 }} />}
      {embedUrl && (
        <iframe
          src={embedUrl}
          style={{ width: '100%', height: '70vh', border: 'none' }}
          onLoad={() => setLoading(false)}
          title={service?.name}
        />
      )}
    </Modal>
  );
};

export default IntegrationIframeViewer;
