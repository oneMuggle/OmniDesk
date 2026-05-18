import { useState, useEffect } from 'react';
import { Modal, Spin, Tag, Typography } from 'antd';
import PropTypes from 'prop-types';
import { previewDocument } from '../api/smartAssistantApi';
import './DocumentPreview.css';

const { Paragraph } = Typography;

const DocumentPreview = ({ visible, document: doc, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [previewContent, setPreviewContent] = useState('');
  const [previewType, setPreviewType] = useState('');

  useEffect(() => {
    if (!visible || !doc) return;

    const loadPreview = async () => {
      setLoading(true);
      try {
        const response = await previewDocument(doc.id);
        if (response.data && response.data.content) {
          setPreviewContent(response.data.content);
          setPreviewType('text');
        } else {
          setPreviewType('pdf');
        }
      } catch {
        setPreviewContent('预览加载失败');
        setPreviewType('text');
      } finally {
        setLoading(false);
      }
    };
    loadPreview();
  }, [visible, doc]);

  const ext = doc?.file ? doc.file.split('.').pop().toLowerCase() : '';
  const isPdf = ext === 'pdf';

  const fileUrl = doc?.file || '';

  return (
    <Modal
      title={`文档预览: ${doc?.title || ''}`}
      open={visible}
      onCancel={onClose}
      footer={null}
      width={800}
      className="document-preview-modal"
    >
      {loading ? (
        <div className="preview-loading">
          <Spin size="large" />
          <p>加载预览中...</p>
        </div>
      ) : previewType === 'text' ? (
        <div className="preview-text">
          <Paragraph>{previewContent}</Paragraph>
        </div>
      ) : isPdf ? (
        <div className="preview-pdf">
          <iframe src={fileUrl} title="PDF预览" width="100%" height="600px" />
        </div>
      ) : (
        <div className="preview-unsupported">
          <Tag color="warning">不支持在线预览</Tag>
          <p>该文件格式暂不支持预览，请下载后查看。</p>
        </div>
      )}
    </Modal>
  );
};

export default DocumentPreview;

DocumentPreview.propTypes = {
  visible: PropTypes.bool,
  document: PropTypes.shape({
    id: PropTypes.number,
    title: PropTypes.string,
    file: PropTypes.string,
  }),
  onClose: PropTypes.func,
};
