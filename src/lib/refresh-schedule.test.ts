import { describe, expect, it } from 'vitest';

import { isPlanRefreshWindow, PLAN_REFRESH_INTERVAL_MS } from './refresh-schedule';


describe('automatic plan refresh schedule', () => {
  it('uses a five-minute interval', () => {
    expect(PLAN_REFRESH_INTERVAL_MS).toBe(300_000);
  });

  it('allows refreshes from 06:00 until before 22:00 in Berlin', () => {
    expect(isPlanRefreshWindow(new Date('2026-08-22T04:00:00Z'))).toBe(true);
    expect(isPlanRefreshWindow(new Date('2026-08-22T19:59:00Z'))).toBe(true);
  });

  it('pauses refreshes from 22:00 until before 06:00 in Berlin', () => {
    expect(isPlanRefreshWindow(new Date('2026-08-22T20:00:00Z'))).toBe(false);
    expect(isPlanRefreshWindow(new Date('2026-08-23T03:59:00Z'))).toBe(false);
  });
});
