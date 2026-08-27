import { ApiError, submitGateAnswer } from './api';
import { forgetGateAnswer, loadGateAnswer } from './storage';
import type { AuthStatus } from './types';

export async function restoreStoredAccess(status: AuthStatus): Promise<AuthStatus> {
  if (status.authorized || status.blocked) return status;

  const storedAnswer = loadGateAnswer();
  if (!storedAnswer) return status;

  try {
    await submitGateAnswer(storedAnswer);
    return { authorized: true, blocked: false, remainingAttempts: 3 };
  } catch (error) {
    if (error instanceof ApiError && error.code === 'invalid_answer') {
      forgetGateAnswer();
      return {
        authorized: false,
        blocked: false,
        remainingAttempts: Number(error.details.remainingAttempts ?? 0),
      };
    }
    if (error instanceof ApiError && error.code === 'ip_blocked') {
      forgetGateAnswer();
      return { authorized: false, blocked: true, remainingAttempts: 0 };
    }
    throw error;
  }
}
