import React from 'react';
import DocumentProcessor from './DocumentProcessor';
import { Typography } from 'antd';

const { Title } = Typography;

const OfficeAssistant = () => {
  return (
    <div style={{ padding: '24px' }}>
      <Title level={2}>Office 助手</Title>
      <p>欢迎使用 Office 助手。请使用以下工具处理您的文档。</p>
      <DocumentProcessor />
    </div>
  );
};

export default OfficeAssistant;