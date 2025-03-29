export const handleResponse = (response) => {
  if (response.status >= 200 && response.status < 300) {
    return response.data;
  }
  const error = new Error(response.statusText);
  error.response = response;
  throw error;
};

export const handleError = (error) => {
  console.error('API call failed:', error);
  if (error.response) {
    console.error('Response data:', error.response.data);
    console.error('Response status:', error.response.status);
    console.error('Response headers:', error.response.headers);
  } else if (error.request) {
    console.error('No response received:', error.request);
  }
  throw error;
};
