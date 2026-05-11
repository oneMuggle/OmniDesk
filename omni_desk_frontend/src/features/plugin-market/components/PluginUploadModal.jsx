import { useState } from 'react';
import { Modal, Upload, Form, Input, Button, message, Alert } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import { uploadPluginVersion } from '../api/pluginApi';
import { validateManifest } from '../utils/pluginValidator';

const { Dragger } = Upload;

const PluginUploadModal = ({ plugin, onClose, onSuccess }) => {
  const [uploading, setUploading] = useState(false);
  const [fileList, setFileList] = useState([]);
  const [manifestText, setManifestText] = useState('');
  const [validationError, setValidationError] = useState('');

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.warning('请选择插件文件');
      return;
    }

    if (manifestText) {
      const error = validateManifest(manifestText);
      if (error) {
        setValidationError(error);
        return;
      }
      setValidationError('');
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', fileList[0].originFileObj);
      if (manifestText) {
        formData.append('manifest', manifestText);
      }

      await uploadPluginVersion(plugin.id, formData);
      message.success('版本上传成功');
      onSuccess();
      onClose();
    } catch {
      message.error('版本上传失败');
    } finally {
      setUploading(false);
    }
  };

  const uploadProps = {
    onRemove: () => setFileList([]),
    beforeUpload: (file) => {
      if (!file.name.endsWith('.zip')) {
        message.error('仅支持 .zip 文件');
        return false;
      }
      setFileList([file]);
      return false;
    },
    fileList,
    maxCount: 1,
  };

  return (
    <Modal
      title={`上传版本 - ${plugin.name}`}
      open
      onCancel={onClose}
      footer={
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <Button onClick={onClose}>取消</Button>
          <Button
            type="primary"
            loading={uploading}
            onClick={handleUpload}
            disabled={fileList.length === 0}
          >
            上传
          </Button>
        </div>
      }
    >
      <Form layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item label="插件文件（.zip）">
          <Dragger {...uploadProps}>
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p>点击或拖拽文件到此区域</p>
            <p style={{ color: '#999', fontSize: 12 }}>仅支持 .zip 格式</p>
          </Dragger>
        </Form.Item>
        <Form.Item label="插件清单（可选，JSON 格式）">
          <Input.TextArea
            rows={6}
            value={manifestText}
            onChange={(e) => setManifestText(e.target.value)}
            placeholder={`{
  "name": "${plugin.name}",
  "version": "1.0.0",
  "entry_point": "main",
  "protocol": "stdio",
  "timeout": 30
}`}
          />
        </Form.Item>
        {validationError && (
          <Alert message={validationError} type="error" showIcon style={{ marginBottom: 16 }} />
        )}
      </Form>
    </Modal>
  );
};

export default PluginUploadModal;
