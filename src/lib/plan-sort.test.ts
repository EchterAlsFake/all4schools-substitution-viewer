import { describe, expect, it } from 'vitest';

import type { PlanEntry } from './types';
import { sortEntriesByClass } from './plan-sort';


function entry(id: string, classCode: string, start: string): PlanEntry {
  return {
    id,
    kind: 'change',
    start,
    end: start,
    oldSubject: '',
    newSubject: '',
    oldRooms: [],
    newRooms: [],
    classes: [classCode],
    comment: '',
  };
}

describe('plan entry ordering', () => {
  it('orders grades from 5 through 12 and accepts leading zeroes', () => {
    const entries = [
      entry('upper', '12_GES4', '2026-08-24T09:40:00+02:00'),
      entry('unknown', 'EXTERNAL', '2026-08-24T07:45:00+02:00'),
      entry('middle', '09c', '2026-08-24T10:30:00+02:00'),
      entry('lower', '5b', '2026-08-24T08:35:00+02:00'),
    ];

    expect(sortEntriesByClass(entries).map((item) => item.id)).toEqual([
      'lower',
      'middle',
      'upper',
      'unknown',
    ]);
  });

  it('keeps entries in chronological order within the same grade', () => {
    const entries = [
      entry('later', '7b', '2026-08-24T10:30:00+02:00'),
      entry('earlier', '07a', '2026-08-24T07:45:00+02:00'),
    ];

    expect(sortEntriesByClass(entries).map((item) => item.id)).toEqual([
      'earlier',
      'later',
    ]);
  });
});
