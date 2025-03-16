import React, { useState, useRef, useEffect } from 'react';
import { Button, Input, Spin, FloatButton, Popover } from 'antd';
import { CommentOutlined, SendOutlined, CloseOutlined } from '@ant-design/icons';
import { createClient } from '../api/deepseek';
import './ChatInterface.css';

const deepseekClient = createClient();

const ChatInterface = () => {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!inputText.trim()) return;

    const newMessage = { role: 'user', content: inputText };
    setMessages(prev => [...prev, newMessage]);
    setInputText('');
    setLoading(true);

    try {
      const completion = await deepseekClient.chat.completions.create({
        model: 'deepseek-chat',
        messages: [
          { role: 'system', content: '你是一个专业的文档助手，帮助用户分析和修改文档内容' },
          ...messages,
          newMessage
        ],
        stream: false,
      });

      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: completion.choices[0].message.content }
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
              <Button
                type="primary"
                icon={<SendOutlined />}
                onClick={handleSend}
                disabled={loading}
              />
            </div>
          </div>
        }
        title={
          <div className="chat-header">
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
      />
    </div>
  );
};

export default ChatInterface;
