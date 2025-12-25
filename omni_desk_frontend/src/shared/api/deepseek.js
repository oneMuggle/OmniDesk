export const createClient = () => {
  // Mocking DeepSeek client creation
  return {
    chat: {
      completions: {
        create: async () => {
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