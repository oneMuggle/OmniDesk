export const createClient = (apiConfig) => {
  // Mocking DeepSeek client creation
  return {
    chat: {
      completions: {
        create: async (payload) => {
          // Mock response
          return {
            choices: [
              {
                message: {
                  role: 'assistant',
                  content: 'This is a mock response from DeepSeek.',
                },
              },
            ],
          };
        },
      },
    },
  };
};