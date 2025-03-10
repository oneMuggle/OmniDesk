import React, { useState } from 'react';
import { Upload, Button, message } from 'antd';
import mammoth from 'mammoth';
import { InboxOutlined } from '@ant-design/icons';
import ChatInterface from './ChatInterface';
import './DocumentsPage.css';

const { Dragger } = Upload;

const DocumentsPage = () => {
  const [htmlContent, setHtmlContent] = useState('');
  const [uploading, setUploading] = useState(false);

  const beforeUpload = (file) => {
    const isDocx = file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    if (!isDocx) {
      message.error('仅支持.docx文件格式!');
    }
    return isDocx;
  };

  const handleConvert = (file) => {
    setUploading(true);
    const reader = new FileReader();
    
    reader.onload = async (e) => {
      try {
        const arrayBuffer = e.target.result;
        const result = await mammoth.convertToHtml({ arrayBuffer });
        setHtmlContent(result.value);
        message.success('文档转换成功!');
      } catch (error) {
        message.error('文档解析失败: ' + error.message);
      } finally {
        setUploading(false);
      }
    };

    reader.readAsArrayBuffer(file);
  };

  return (
    <div className="documents-container">
      <ChatInterface />
      <div className="upload-section">
        <Dragger
          name="file"
          multiple={false}
          beforeUpload={beforeUpload}
          customRequest={({ file }) => handleConvert(file)}
          showUploadList={false}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
          <p className="ant-upload-hint">仅支持.docx格式文档</p>
        </Dragger>
      </div>

      {htmlContent && (
        <div className="preview-section">
          <div 
            className="content-preview"
            dangerouslySetInnerHTML={{ __html: htmlContent }}
          />
          <Button 
            type="primary" 
            onClick={() => setHtmlContent('')}
            style={{ marginTop: 16 }}
          >
            清除内容
          </Button>
        </div>
      )}
    </div>
  );
};

export default DocumentsPage;
