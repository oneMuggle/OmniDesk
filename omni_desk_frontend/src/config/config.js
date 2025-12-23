const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || '/api';
const WEBSOCKET_URL = 'ws://localhost:8000/ws/chat/';
const RAGFLOW_API_BASE_URL = 'http://localhost:8001/api/v1';
const DEEPSEEK_API_URL = 'YOUR_DEEPSEEK_API_URL';
const DEEPSEEK_API_KEY = 'YOUR_DEEPSEEK_API_KEY';
const OLLAMA_API_URL = 'http://localhost:11434/api';

export {
  API_BASE_URL,
  WEBSOCKET_URL,
  RAGFLOW_API_BASE_URL,
  DEEPSEEK_API_URL,
  DEEPSEEK_API_KEY,
  OLLAMA_API_URL,
};