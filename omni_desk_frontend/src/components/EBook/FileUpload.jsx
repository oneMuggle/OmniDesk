import React from 'react';
import { Upload, Button, message } from 'antd';
import { UploadOutlined } from '@ant-design/icons';

const FileUpload = ({ onFileUpload }) => {
  const props = {
    accept: '.md',
    beforeUpload: file => {
      onFileUpload(file);
      message.success(`'${file.name}' 已选择`);
      return false; // Prevent automatic upload
    },
    showUploadList: false,
  };

  return (
    <Upload {...props}>
      <Button icon={<UploadOutlined />}>选择文件</Button>
    </Upload>
  );
};

export default FileUpload;