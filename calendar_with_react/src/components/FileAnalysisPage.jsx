import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faFileAlt, faUpload } from '@fortawesome/free-solid-svg-icons';

function FileAnalysisPage() {
  const { isAuthenticated } = useAuth();
  const [file, setFile] = useState(null);
  const [analysisResult, setAnalysisResult] = useState(null);

  const handleFileChange = (e) => {
    setFile(e.target.files[0]);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    
    // TODO: 实现文件上传和解析逻辑
    console.log('上传文件:', file.name);
    
    // 模拟解析结果
    setAnalysisResult({
      fileName: file.name,
      people: [
        { name: '张三', origin: '北京', age: 30 },
        { name: '李四', origin: '上海', age: 25 }
      ]
    });
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
