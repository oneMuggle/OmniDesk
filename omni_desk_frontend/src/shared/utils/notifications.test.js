import { showNotification } from './notifications';

describe('notifications utils', () => {
  it('showNotification should be a function', () => {
    expect(typeof showNotification).toBe('function');
  });
});
