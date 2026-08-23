import type { Preferences, SubjectOverrides } from './types';

export const defaultPreferences: Preferences = {
  enabled: false,
  grade: '',
  classLetter: '',
  courses: [],
};

export function readStorage<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

export function writeStorage(key: string, value: unknown): boolean {
  try {
    localStorage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function loadPreferences(): Preferences {
  const stored = readStorage<Partial<Preferences>>('vplan-preferences', {});
  return {
    enabled: stored.enabled === true,
    grade: typeof stored.grade === 'string' ? stored.grade : '',
    classLetter: typeof stored.classLetter === 'string' ? stored.classLetter : '',
    courses: Array.isArray(stored.courses)
      ? stored.courses.filter((course): course is string => typeof course === 'string')
      : [],
  };
}

export function loadOverrides(): SubjectOverrides {
  return readStorage<SubjectOverrides>('vplan-subject-overrides', {});
}
