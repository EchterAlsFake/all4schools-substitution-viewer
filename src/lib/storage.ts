import type { Preferences, SubjectOverrides } from './types';

export const GATE_ANSWER_STORAGE_KEY = 'vplan-gate-answer';
export const TRANSPARENCY_NOTICE_STORAGE_KEY = 'vplan-transparency-notice-seen-v1';

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

export function removeStorage(key: string): boolean {
  try {
    localStorage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}

export function loadGateAnswer(): string | null {
  const stored = readStorage<unknown>(GATE_ANSWER_STORAGE_KEY, null);
  if (
    typeof stored === 'string'
    && stored.trim().length > 0
    && stored.length <= 32
    && !Array.from(stored).some((character) => character.charCodeAt(0) < 32)
  ) {
    return stored;
  }
  removeStorage(GATE_ANSWER_STORAGE_KEY);
  return null;
}

export function rememberGateAnswer(answer: string): boolean {
  return writeStorage(GATE_ANSWER_STORAGE_KEY, answer.trim());
}

export function forgetGateAnswer(): boolean {
  return removeStorage(GATE_ANSWER_STORAGE_KEY);
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
