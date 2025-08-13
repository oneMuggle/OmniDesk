import React, { useState, useRef, useEffect } from 'react';
import { useDrag } from 'react-dnd'; // 确保这个包已安装
import { Button, Input, Spin, FloatButton, Popover, Upload } from 'antd';
import { CommentOutlined, SendOutlined, CloseOutlined, UploadOutlined } from '@ant-design/icons';
import { useApi } from '../context/ApiProvider';
import { createClient } from '../api/deepseek';
import { chatCompletion as ollamaChat } from '../api/ollama';
import './ChatInterface.css';


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
      let response;
      if (apiType === 'ollama') {
        response = await ollamaChat(apiConfig, [
          { 
            role: 'system', 
            content: `你是一个专业的文档助手，请根据用户提供的文档内容进行分析和修改：
${newMessage.files?.join('\n\n') || ''}
用户需求：${newMessage.content}`
          },
          ...messages,
          newMessage
        ]);
      } else if (apiType === 'deepseek') {
        const client = createClient(); // createClient现在从ApiProvider获取配置
        response = await client.chat.completions.create({
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
        response = response.choices[0].message;
      } else if (apiType === 'ragflow') {
        // Ragflow API 调用逻辑
        // 注意：这里需要根据Ragflow的实际API接口调整
        // 假设Ragflow的API端点从apiConfig中获取，并且有一个/query接口
        const ragflowResponse = await fetch(`${apiConfig.ragflow.apiEndpoint}/query`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiConfig.ragflow.apiKey}`
          },
          body: JSON.stringify({
            question: newMessage.content,
            // 如果Ragflow支持文件内容作为上下文，可以在这里添加
            files: newMessage.files
          })
        });
        const ragflowData = await ragflowResponse.json();
        response = { content: ragflowData.answer }; // 假设Ragflow返回的答案在'answer'字段
      } else if (apiType === 'dify') {
        // Dify API 调用逻辑
        // 注意：这里需要根据Dify的实际API接口调整
        // 假设Dify的API端点从apiConfig中获取，并且有一个/chat接口
        const difyResponse = await fetch(`${apiConfig.dify.apiEndpoint}/chat`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${apiConfig.dify.apiKey}`
          },
          body: JSON.stringify({
            inputs: {
              query: newMessage.content
            },
            // 如果Dify支持文件内容作为上下文，可以在这里添加
            // files: newMessage.files
          })
        });
        const difyData = await difyResponse.json();
        response = { content: difyData.answer }; // 假设Dify返回的答案在'answer'字段
      }

      setMessages(prev => [
        ...prev,
        { 
          role: 'assistant', 
          content: response.content,
          ...(response.context && { context: response.context })
        }
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
            <span>智能问答助手</span>
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
