import type { AuthStatus, PlanResponse } from './types';

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    public readonly status: number,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(code);
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    credentials: 'same-origin',
    referrerPolicy: 'no-referrer',
    ...init,
  });
  const payload = (await response.json().catch(() => ({}))) as Record<string, unknown>;
  if (!response.ok) {
    throw new ApiError(String(payload.code || 'request_failed'), response.status, payload);
  }
  return payload as T;
}

export function getAuthStatus(): Promise<AuthStatus> {
  return requestJson<AuthStatus>('/api/auth/status');
}

export function submitGateAnswer(answer: string): Promise<{ authorized: true }> {
  return requestJson('/api/auth/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answer }),
  });
}

export function getPlan(): Promise<PlanResponse> {
  return requestJson<PlanResponse>('/api/plan');
}

export function logout(): Promise<{ ok: true }> {
  return requestJson('/api/auth/logout', { method: 'POST' });
}

export function sendFeedback(message: string): Promise<{ ok: true }> {
  return requestJson('/api/feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-VPlan-Request': 'feedback',
    },
    body: JSON.stringify({ message, privacy_confirmed: true }),
  });
}
