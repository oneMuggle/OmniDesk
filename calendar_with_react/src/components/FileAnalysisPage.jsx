import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFileAlt, faUpload } from '@fortawesome/free-solid-svg-icons';
import { documentAPI } from '../api/documents';

function FileAnalysisPage() {
  const { isAuthenticated } = useAuth();
  const [file, setFile] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

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
      
      const response = await documentAPI.analyzeFile(formData);
      setAnalysisResult(response.data);
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
            <h3><FontAwesomeIcon icon={faUpload} /> 上传文件</h3>
            <form onSubmit={handleSubmit}>
              <input 
                type="file" 
                accept=".docx,.xlsx,.pdf" 
                onChange={handleFileChange}
              />
              <button type="submit">分析文件</button>
            </form>
          </div>

          {analysisResult && (
            <div className="result-section">
              <h3>分析结果</h3>
              <div>文件名: {analysisResult.fileName}</div>
              <ul>
                {analysisResult.people.map((person, index) => (
                  <li key={index}>
                    {person.name} - {person.origin} - {person.age}岁
                  </li>
                ))}
              </ul>
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
