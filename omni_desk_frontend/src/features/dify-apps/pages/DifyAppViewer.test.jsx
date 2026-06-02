import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

describe('DifyAppViewer', () => {
  it('should be importable', async () => {
    const DifyAppViewer = await import('./DifyAppViewer');
    expect(DifyAppViewer).toBeDefined();
  });
});
