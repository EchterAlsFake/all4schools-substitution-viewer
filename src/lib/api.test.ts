import { afterEach, describe, expect, it, vi } from 'vitest';

import { getPlan, submitGateAnswer } from './api';


describe('same-origin API client', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('submits the gate answer only to the backend JSON endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ authorized: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await submitGateAnswer('ROOM42');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/answer',
      expect.objectContaining({
        credentials: 'same-origin',
        method: 'POST',
        body: JSON.stringify({ answer: 'ROOM42' }),
      }),
    );
  });

  it('keeps language-neutral backend error codes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: 'authentication_required' }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    await expect(getPlan()).rejects.toEqual(
      expect.objectContaining({ code: 'authentication_required', status: 401 }),
    );
  });
});
