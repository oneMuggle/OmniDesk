/**
 * 项目文档上传按钮
 *
 * 上传到 paperless outbox,成功后显示同步状态徽章。
 */
import { useState } from 'react';
import { Upload, Button, message, Space } from 'antd';
import { UploadOutlined } from '@ant-design/icons';
import PropTypes from 'prop-types';
import axiosInstance from '../../../shared/api/axiosConfig';
import SyncStatusBadge from '../../documents-library/components/SyncStatusBadge';

const uploadDocument = async (projectId, file, title) => {
  const formData = new FormData();
  formData.append('file', file);
  if (title) formData.append('title', title);

  const { data } = await axiosInstance.post(
    `projects/${projectId}/upload_document/`,
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
};

export default function DocumentUploadButton({ projectId, title, onSuccess }) {
  const [uploading, setUploading] = useState(false);
  const [syncStatus, setSyncStatus] = useState(null);

  const handleUpload = async (options) => {
    const { file } = options;
    setUploading(true);
    setSyncStatus(null);
    try {
      const result = await uploadDocument(projectId, file, title);
      setSyncStatus(result.status || 'pending');
      message.success('上传成功,文档将在后台同步到 paperless');
      onSuccess?.(result);
    } catch (error) {
      const msg = error.response?.data?.detail
        || error.response?.data?.message
        || error.message
        || '上传失败';
      message.error(msg);
    } finally {
      setUploading(false);
    }
  };

  return (
    <Space>
      <Upload
        customRequest={handleUpload}
        showUploadList={false}
        disabled={uploading}
      >
        <Button icon={<UploadOutlined />} loading={uploading}>
          {uploading ? '上传中...' : '上传文档'}
        </Button>
      </Upload>
      {syncStatus && <SyncStatusBadge status={syncStatus} />}
    </Space>
  );
}

DocumentUploadButton.propTypes = {
  projectId: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
  title: PropTypes.string,
  onSuccess: PropTypes.func,
};
