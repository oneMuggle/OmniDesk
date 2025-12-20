import apiClient from './apiClient';

/**
 * Process text using the office assistant AI.
 * @param {string} text The text to process.
 * @param {string} action The action to perform (e.g., 'proofread', 'translate', 'polish').
 * @returns {Promise<any>}
 */
export const processText = (text, action) => {
  return apiClient.post('/office_assistant/process/', {
    text,
    action,
  });
};