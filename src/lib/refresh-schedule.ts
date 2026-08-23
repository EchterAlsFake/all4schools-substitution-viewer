export const PLAN_REFRESH_INTERVAL_MS = 5 * 60 * 1_000;

const berlinHourFormatter = new Intl.DateTimeFormat('en-GB', {
  hour: '2-digit',
  hourCycle: 'h23',
  timeZone: 'Europe/Berlin',
});

export function isPlanRefreshWindow(now: Date = new Date()): boolean {
  const hour = Number(berlinHourFormatter.format(now));
  return hour >= 6 && hour < 22;
}
