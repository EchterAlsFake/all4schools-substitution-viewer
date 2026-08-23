import type { PlanEntry } from './types';


function entryGrade(entry: PlanEntry): number {
  const grades = entry.classes
    .map((classCode) => classCode.trim().match(/^0*(\d{1,2})(?=\D|$)/)?.[1])
    .map((grade) => Number(grade))
    .filter((grade) => Number.isInteger(grade) && grade >= 5 && grade <= 12);
  return grades.length ? Math.min(...grades) : Number.POSITIVE_INFINITY;
}

export function sortEntriesByClass(entries: PlanEntry[]): PlanEntry[] {
  return [...entries].sort((left, right) => {
    const gradeDifference = entryGrade(left) - entryGrade(right);
    if (gradeDifference) return gradeDifference;

    const timeDifference = left.start.localeCompare(right.start);
    if (timeDifference) return timeDifference;

    const leftClasses = [...left.classes].sort((a, b) =>
      a.localeCompare(b, 'de', { numeric: true }),
    ).join(' ');
    const rightClasses = [...right.classes].sort((a, b) =>
      a.localeCompare(b, 'de', { numeric: true }),
    ).join(' ');
    return leftClasses.localeCompare(rightClasses, 'de', { numeric: true });
  });
}
