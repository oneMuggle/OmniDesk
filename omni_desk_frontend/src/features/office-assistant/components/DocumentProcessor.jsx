import React, { useState } from 'react';
import { Upload, Button, message, Card, Spin, Row, Col, Select } from 'antd';
import { InboxOutlined } from '@ant-design/icons';
import axiosInstanceInstance from '../../../shared/api/axiosInstanceConfig';
import { logger } from '../../../shared/utils/logger';

const { Dragger } = Upload;
const { Option } = Select;

const DocumentProcessor = () => {
  const [file, setFile] = useState(null);
  const [processing, setProcessing] = useState(false);
  const [result, setResult] = useState(null);
  const [action, setAction] = useState('proofread'); // Default action

  const handleFileChange = (info) => {
    // We only take the last file if user selects multiple files
    const latestFile = info.fileList.slice(-1)[0];
    if (latestFile) {
        const { originFileObj } = latestFile;
        const isDocx = originFileObj.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
        if (!isDocx) {
            message.error('只能上传 .docx 文件！');
            setFile(null);
            return;
        }
        setFile(originFileObj);
    } else {
        setFile(null);
    }
  };

  const handleProcess = async () => {
    if (!file) {
      message.error('请先上传文档。');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('action', action);

    setProcessing(true);
    setResult(null);

    try {
      const response = await axiosInstance.post('office-assistant/process-document/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      if (response.data.status === 'success') {
        setResult(response.data.data);
        message.success('文档处理成功。');
      } else {
        message.error(response.data.message || '文档处理失败。');
      }
    } catch (error) {
      message.error('处理文档时发生错误。');
      logger.error('Processing error:', error);
    } finally {
      setProcessing(false);
    }
  };

  const props = {
    name: 'file',
    multiple: false,
    accept: '.docx',
    beforeUpload: () => false, // Prevent auto upload
    onChange: handleFileChange,
    onRemove: () => {
        setFile(null);
    }
  };

  return (
    <div style={{ padding: '24px' }}>
      <Card title="文档处理器">
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <Dragger {...props}>
              <p className="ant-upload-drag-icon">
                <InboxOutlined />
              </p>
              <p className="ant-upload-text">点击或拖拽 .docx 文件到此区域上传</p>
              <p className="ant-upload-hint">
                仅支持单个文件上传。严禁上传公司数据或其他受限文件。
              </p>
            </Dragger>
          </Col>
          <Col>
            <Select value={action} onChange={(value) => setAction(value)} style={{ width: 120, marginRight: 8 }}>
              <Option value="proofread">校对</Option>
              <Option value="polish">润色</Option>
              <Option value="translate">翻译</Option>
            </Select>
            <Button
              type="primary"
              onClick={handleProcess}
              disabled={!file || processing}
              loading={processing}
            >
              处理文档
            </Button>
          </Col>
        </Row>

        {processing && (
          <div style={{ textAlign: 'center', marginTop: '20px' }}>
            <Spin size="large" />
            <p>正在处理，请稍候...</p>
          </div>
        )}

        {result && (
          <div style={{ marginTop: '24px' }}>
            <Card title="原文">
              <p>{result.original_text}</p>
            </Card>
            <Card title="处理结果" style={{ marginTop: '16px' }}>
              <p>{result.processed_text}</p>
            </Card>
          </div>
        )}
      </Card>
    </div>
  );
};

export default DocumentProcessor;