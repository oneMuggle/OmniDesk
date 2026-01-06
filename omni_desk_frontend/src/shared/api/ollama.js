import apiClient from './apiClient';

export const chatCompletion = async (apiConfig, messages, onData) => {
  try {
    const response = await fetch('ollama/chat/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        config: apiConfig,
        messages: messages,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    if (!response.body) {
      throw new Error('Response body is null');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let fullContent = '';

    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); 

      for (const line of lines) {
        if (line.trim() === '') continue;
        try {
          const json = JSON.parse(line);
          fullContent = json.content; 
          onData({
            content: fullContent,
            context: json.context,
            done: json.done,
          });
          if (json.done) {
            return;
          }
        } catch (e) {
          console.error('Failed to parse JSON line from stream:', line, e);
        }
      }
    }
  } catch (error) {
    console.error('Error during chat completion:', error);
    throw error;
  }
};

export const getOllamaConfigs = () => {
  return apiClient.get('ollama/configs/');
};

export const addOllamaConfig = (config) => {
  return apiClient.post('ollama/configs/', config);
};

export const updateOllamaConfig = (id, config) => {
  return apiClient.put(`ollama/configs/${id}/`, config);
};

export const deleteOllamaConfig = (id) => {
  return apiClient.delete(`ollama/configs/${id}/`);
};

export const getOllamaModelsFromEndpoint = (apiEndpoint) => {
  return apiClient.post('ollama/fetch-models/', { api_endpoint: apiEndpoint });
};

export const getModels = () => {
  return getOllamaConfigs();
};