import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, expect, it, vi } from 'vitest';

import Gate from './Gate.svelte';


afterEach(() => vi.unstubAllGlobals());

it('uses a labelled form and unlocks only after a successful backend response', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ authorized: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    ),
  );
  const onAuthorized = vi.fn();
  render(Gate, {
    status: { authorized: false, blocked: false, remainingAttempts: 3 },
    serviceError: false,
    onAuthorized,
  });

  await fireEvent.input(screen.getByLabelText('gate.question'), { target: { value: 'ROOM42' } });
  await fireEvent.click(screen.getByRole('button', { name: 'gate.submit' }));

  await waitFor(() => expect(onAuthorized).toHaveBeenCalledOnce());
});
