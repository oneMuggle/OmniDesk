import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFileAlt, faUpload } from '@fortawesome/free-solid-svg-icons';
import documentsApi from '../api/documents';
import './FileAnalysisPage.css';

function FileAnalysisPage() {
  const { isAuthenticated } = useAuth();
  const [file, setFile] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [templateId, setTemplateId] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
  
    setIsLoading(true);
    setError(null);
  
    try {
      const formData = new FormData();
      formData.append('file', file);
      const uploadResponse = await documentsApi.uploadTemplate(formData);
  
      if (uploadResponse && uploadResponse.id) {
        setTemplateId(uploadResponse.id);
        const analysisResponse = await documentsApi.analyzeDocumentTemplate(uploadResponse.id);
        setAnalysisResult(analysisResponse);
      } else {
        throw new Error('文件上传后未收到模板ID');
      }
    } catch (err) {
      setError('文件分析失败，请重试');
      console.error('分析错误:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="file-analysis-page">
      <h2><FontAwesomeIcon icon={faFileAlt} /> 文件分析</h2>
      
      {isAuthenticated ? (
        <>
          <div className="upload-section">
            <h3><FontAwesomeIcon icon={faUpload} /> 上传并分析文件</h3>
            <form onSubmit={handleSubmit} className="upload-form">
              <label className="file-input-wrapper">
                {file ? `已选择: ${file.name}` : '选择文件'}
                <input
                  type="file"
                  accept=".docx,.xlsx,.pdf"
                  onChange={handleFileChange}
                />
              </label>
              {file && <div className="file-name">{file.name}</div>}
              <button
                type="submit"
                className="analyze-button"
                disabled={!file || isLoading}
              >
                {isLoading ? '分析中...' : '分析文件'}
              </button>
            </form>
          </div>

          {isLoading && <div className="loading-message">正在分析文件，请稍候...</div>}
          {error && <div className="error-message">{error}</div>}

          {analysisResult && (
            <div className="result-section">
              <h3>分析结果</h3>
              <div className="result-card">
                <pre>{JSON.stringify(analysisResult, null, 2)}</pre>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="login-required">
          请登录后使用文件分析功能
        </div>
      )}
    </div>
  );
}

export default FileAnalysisPage;
