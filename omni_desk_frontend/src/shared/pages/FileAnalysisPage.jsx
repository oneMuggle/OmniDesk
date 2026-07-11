import React, { useState, useCallback } from 'react';
import { Card, message, Spin, Typography } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';
import FileUploadSection from '../components/file-processing/FileUploadSection';
import PreviewSection from '../components/file-processing/PreviewSection';
import AIAnalysisSection from '../components/file-processing/AIAnalysisSection';
import { fileProcessingApi } from '../api/fileProcessing';
import './FileAnalysisPage.css';

const { Text } = Typography;

/** 轮询配置 */
const POLL_MAX_ATTEMPTS = 30;
const POLL_INTERVAL_MS = 1000;

const FileAnalysisPage = () => {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [previewData, setPreviewData] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [processingStatus, setProcessingStatus] = useState('');

  /**
   * 轮询处理状态，直到 status=completed / failed 或超时
   * @param {string} fileId
   * @returns {Promise<object>} 预览数据
   */
  const pollProcessingStatus = useCallback(async (fileId) => {
    for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt++) {
      const result = await fileProcessingApi.getPreview(fileId);

      if (result.status === 'completed') {
        return result;
      }

      if (result.status === 'failed') {
        throw new Error(result.error || '文件处理失败');
      }

      setProcessingStatus(result.status || `处理中 (${attempt + 1}/${POLL_MAX_ATTEMPTS})`);
      await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
    }

    throw new Error('处理超时，请稍后重试');
  }, []);

  /**
   * 处理文件上传 — 完整工作流：上传 → 轮询 → 分析
   * @param {File} file
   */
  const handleFileUpload = useCallback(async (file) => {
    setLoading(true);
    setProcessingStatus('正在上传...');
    setUploadedFile(null);
    setPreviewData(null);
    setAnalysisResult(null);

    try {
      // 1. 上传文件
      const uploadResult = await fileProcessingApi.upload(file);
      setUploadedFile(uploadResult);

      // 2. 轮询处理状态
      setProcessingStatus('正在处理...');
      const preview = await pollProcessingStatus(uploadResult.id);
      setPreviewData(preview);

      // 3. 自动生成 AI 摘要
      setProcessingStatus('正在分析...');
      const analysis = await fileProcessingApi.analyze(uploadResult.id);
      setAnalysisResult(analysis);

      setProcessingStatus('');
      message.success('文件处理成功');
    } catch (err) {
      setProcessingStatus('');
      message.error(err.message || '文件处理失败');
    } finally {
      setLoading(false);
    }
  }, [pollProcessingStatus]);

  /**
   * 自然语言查询
   * @param {string} question
   * @returns {Promise<string>} 查询结果
   */
  const handleQuery = useCallback(async (question) => {
    if (!uploadedFile) return;

    try {
      const result = await fileProcessingApi.query(uploadedFile.id, question);
      return result.answer;
    } catch (err) {
      message.error('查询失败，请重试');
      throw err;
    }
  }, [uploadedFile]);

  return (
    <div className="file-analysis-page">
      <Card title="文件分析" style={{ marginBottom: 16 }}>
        <FileUploadSection
          onFileUpload={handleFileUpload}
          disabled={loading}
        />

        {loading && (
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 24 }} spin />} />
            <div style={{ marginTop: 8 }}>
              <Text type="secondary">{processingStatus}</Text>
            </div>
          </div>
        )}
      </Card>

      {previewData && (
        <Card title="数据预览" style={{ marginBottom: 16 }}>
          <PreviewSection
            data={previewData}
            mimeType={uploadedFile?.mime_type}
          />
        </Card>
      )}

      {analysisResult && (
        <Card title="AI 分析" style={{ marginBottom: 16 }}>
          <AIAnalysisSection
            summary={analysisResult}
            onQuery={handleQuery}
          />
        </Card>
      )}
    </div>
  );
};

export default FileAnalysisPage;
