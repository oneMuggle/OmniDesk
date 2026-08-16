import React from 'react';
import { Upload, Typography } from 'antd';
import { InboxOutlined, FileExcelOutlined, FileWordOutlined, FilePdfOutlined } from '@ant-design/icons';
import { notifications } from '../../utils/notifications';
import { validateFileSize } from '../../utils/upload';

const { Dragger } = Upload;
const { Text } = Typography;

const SUPPORTED_FORMATS = [
  { ext: '.xlsx, .xls, .csv', icon: <FileExcelOutlined />, label: 'Excel 表格' },
  { ext: '.docx, .doc', icon: <FileWordOutlined />, label: 'Word 文档' },
  { ext: '.pdf', icon: <FilePdfOutlined />, label: 'PDF 文档' },
];

const FileUploadSection = ({ onFileUpload, disabled }) => {
  const uploadProps = {
    name: 'file',
    multiple: false,
    maxCount: 1,
    accept: '.xlsx,.xls,.csv,.docx,.doc,.pdf',
    showUploadList: false,
    disabled,
    beforeUpload: (file) => {
      // R4-B5: 文件大小校验走公共 util(与 FileAttachmentInput 同源)
      const sizeCheck = validateFileSize(file);
      if (!sizeCheck.ok) {
        notifications.showError(sizeCheck.reason);
        return Upload.LIST_IGNORE;
      }

      // 触发上传回调
      onFileUpload(file);
      return false; // 阻止自动上传
    },
  };

  return (
    <div className="file-upload-section">
      <Dragger {...uploadProps}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">
          支持格式：Excel (.xlsx, .xls, .csv)、Word (.docx, .doc)、PDF (.pdf)
        </p>
      </Dragger>

      <div style={{ marginTop: 16 }}>
        <Text type="secondary">支持的文件类型：</Text>
        <div style={{ marginTop: 8, display: 'flex', gap: 16 }}>
          {SUPPORTED_FORMATS.map((format, index) => (
            <div key={index}>
              {format.icon} <Text>{format.label}</Text>
              <br />
              <Text type="secondary" style={{ fontSize: 12 }}>{format.ext}</Text>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default FileUploadSection;
