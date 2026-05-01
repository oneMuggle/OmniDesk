import { setApiProvider, getApiConfig, clearConversationHistory, createClient } from './deepseek';

jest.mock('axios', () => ({
  post: jest.fn(),
  get: jest.fn(),
  create: jest.fn(),
}));

describe('deepseek API', () => {
  afterEach(() => {
    jest.clearAllMocks();
    clearConversationHistory();
  });

  describe('Configuration', () => {
    it('should get current config', () => {
      // Config is initialized from module-level defaults
      const config = getApiConfig();
      expect(config.model).toBe('deepseek-chat');
      expect(config.apiKey).toBeTruthy();
      expect(config.apiEndpoint).toBeTruthy();
    });

    it('should update config via setApiProvider', () => {
      setApiProvider({ model: 'deepseek-coder' });
      const config = getApiConfig();
      expect(config.model).toBe('deepseek-coder');
    });
  });

  describe('createClient', () => {
    it('should create client with configured endpoint', () => {
      setApiProvider({ apiKey: 'test-key', apiEndpoint: 'https://api.test.com' });
      const client = createClient();
      expect(client.chat.completions).toBeDefined();
    });
  });
});
