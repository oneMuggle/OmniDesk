import { showNotification } from './notifications';

// eslint-disable-next-line jest/no-disabled-tests
describe.skip('notifications utils', () => {
  it('showNotification should be a function', () => {
    expect(typeof showNotification).toBe('function');
  });
});
