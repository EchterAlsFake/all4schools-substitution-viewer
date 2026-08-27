import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { restoreStoredAccess } from './access';
import { GATE_ANSWER_STORAGE_KEY, rememberGateAnswer } from './storage';

describe('stored gate access', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => vi.unstubAllGlobals());

  it('re-checks a remembered answer when the PWA session is missing', async () => {
    rememberGateAnswer('ROOM42');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ authorized: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      restoreStoredAccess({ authorized: false, blocked: false, remainingAttempts: 3 }),
    ).resolves.toEqual({ authorized: true, blocked: false, remainingAttempts: 3 });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/answer',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ answer: 'ROOM42' }),
      }),
    );
  });

  it('discards a remembered answer when the backend rejects it', async () => {
    rememberGateAnswer('STALE');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ code: 'invalid_answer', remainingAttempts: 2 }), {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    );

    await expect(
      restoreStoredAccess({ authorized: false, blocked: false, remainingAttempts: 3 }),
    ).resolves.toEqual({ authorized: false, blocked: false, remainingAttempts: 2 });
    expect(localStorage.getItem(GATE_ANSWER_STORAGE_KEY)).toBeNull();
  });
});
