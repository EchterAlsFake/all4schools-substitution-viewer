export type PlanKind = 'change' | 'cancelled' | 'self_study' | 'unknown';

export interface PlanEntry {
  id: string;
  kind: PlanKind;
  start: string;
  end: string;
  oldSubject: string;
  newSubject: string;
  oldRooms: string[];
  newRooms: string[];
  classes: string[];
  comment: string;
}

export interface PlanDay {
  date: string;
  entries: PlanEntry[];
}

export interface PlanResponse {
  version: string;
  lastSuccessfulFetchAt: string;
  lastAttemptAt: string | null;
  sourceFrom: string;
  sourceTo: string;
  schoolYear: string;
  learnedCourseCodes: string[];
  stale: boolean;
  days: PlanDay[];
}

export interface AuthStatus {
  authorized: boolean;
  blocked: boolean;
  remainingAttempts: number;
}

export interface Preferences {
  enabled: boolean;
  grade: string;
  classLetter: string;
  courses: string[];
}

export interface SubjectOverride {
  name: string;
  teacher: string;
  color: string;
}

export type SubjectOverrides = Record<string, SubjectOverride>;
