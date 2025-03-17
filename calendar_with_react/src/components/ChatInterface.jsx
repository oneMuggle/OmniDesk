import React, { useState, useRef, useEffect } from 'react';
import { useDrag } from 'react-dnd'; // 确保这个包已安装
import { Button, Input, Spin, FloatButton, Popover, Upload } from 'antd';
import { CommentOutlined, SendOutlined, CloseOutlined, UploadOutlined } from '@ant-design/icons';
import { useApi } from '../context/ApiProvider';
import { createClient } from '../api/deepseek';
import { chatCompletion as ollamaChat } from '../api/ollama';
import './ChatInterface.css';

const deepseekClient = createClient();

const ChatInterface = () => {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [fileList, setFileList] = useState([]);
  const [dialogPosition, setDialogPosition] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [dragStartPos, setDragStartPos] = useState({ x: 0, y: 0 });

  const handleMouseDown = (e) => {
    setDragging(true);
    setDragStartPos({
      x: e.clientX - dialogPosition.x,
      y: e.clientY - dialogPosition.y
    });
  };

  const handleMouseMove = (e) => {
    if (dragging) {
      const newX = e.clientX - dragStartPos.x;
      const newY = e.clientY - dragStartPos.y;
      setDialogPosition({ x: newX, y: newY });
    }
  };

  const handleMouseUp = () => {
    setDragging(false);
  };
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const { apiType, apiConfig } = useApi();

  const readFileContent = (file) => {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve({
        name: file.name,
        content: e.target.result
      });
      reader.readAsText(file);
    });
  };

  const handleSend = async () => {
    if (!inputText.trim() && fileList.length === 0) return;

    // 读取所有文件内容
    const fileContents = await Promise.all(
      fileList.map(file => readFileContent(file.originFileObj))
    );

    const newMessage = {
      role: 'user',
      content: inputText,
      files: fileContents.map(f => `${f.name}:\n${f.content.slice(0, 1000)}...`) // 截取前1000字符
    };
    setMessages(prev => [...prev, newMessage]);
    setInputText('');
    setLoading(true);

    try {
      const apiHandler = apiType === 'ollama' ? ollamaChat : createClient(apiConfig).chat.completions;
      
      const response = await apiHandler.create({
        model: apiConfig.model,
        messages: [
          { 
            role: 'system', 
            content: `你是一个专业的文档助手，请根据用户提供的文档内容进行分析和修改：
${newMessage.files?.join('\n\n') || ''}
用户需求：${newMessage.content}`
          },
          ...messages,
          newMessage
        ]
      });

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: response.content }
      ]);
    } catch (error) {
      setMessages(prev => [
        ...prev,
        { role: 'system', content: `错误: ${error.message}` }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-interface">
      <FloatButton
        icon={<CommentOutlined />}
        type="primary"
        onClick={() => setOpen(!open)}
        style={{ right: 24, bottom: 24 }}
      />

      <Popover
        content={
          <div className="chat-panel">
            <div className="messages-container">
              {messages.map((msg, i) => (
                <div key={i} className={`message ${msg.role}`}>
                  <div className="message-bubble">
                    {msg.content.split('\n').map((line, j) => (
                      <p key={j}>{line}</p>
                    ))}
                  </div>
                </div>
              ))}
              {loading && <Spin className="loading-indicator" />}
              <div ref={messagesEndRef} />
            </div>
            
            <div className="input-area">
              <div className="upload-area">
                <Input.TextArea
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onPressEnter={(e) => {
                    e.preventDefault();
                    handleSend();
                  }}
                  placeholder="输入文档修改需求..."
                  autoSize={{ minRows: 1, maxRows: 4 }}
                />
                <Upload
                  accept=".txt,.md,.docx,.pdf"
                  beforeUpload={() => false}
                  fileList={fileList}
                  onChange={({ fileList }) => setFileList(fileList)}
                  multiple
                >
                  <Button type="dashed">上传文件</Button>
                </Upload>
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  onClick={handleSend}
                  disabled={loading}
                />
              </div>
            </div>
          </div>
        }
        title={
          <div 
            className="chat-header"
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{ cursor: 'move' }}
          >
            <span>DeepSeek 文档助手</span>
            <Button 
              type="text" 
              icon={<CloseOutlined />} 
              onClick={() => setOpen(false)}
            />
          </div>
        }
        open={open}
        trigger="click"
        placement="topRight"
        overlayClassName="chat-popover"
        style={{ 
          position: 'fixed',
          left: dialogPosition.x + 'px',
          top: dialogPosition.y + 'px',
          transform: 'none' 
        }}
      />
    </div>
  );
};

export default ChatInterface;
