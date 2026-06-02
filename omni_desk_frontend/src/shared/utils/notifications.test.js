import { showNotification } from './notifications';

describe.skip('notifications utils', () => {
  it('showNotification should be a function', () => {
    expect(typeof showNotification).toBe('function');
  });
});
