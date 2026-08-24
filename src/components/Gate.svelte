<script lang="ts">
  import { ApiError, submitGateAnswer } from '../lib/api';
  import { t } from '../lib/i18n';
  import { rememberGateAnswer } from '../lib/storage';
  import type { AuthStatus } from '../lib/types';

  export let status: AuthStatus;
  export let serviceError = false;
  export let onAuthorized: () => void;

  let answer = '';
  let submitting = false;
  let invalid = false;

  async function submit(): Promise<void> {
    submitting = true;
    invalid = false;
    try {
      await submitGateAnswer(answer);
      rememberGateAnswer(answer);
      onAuthorized();
    } catch (error) {
      if (error instanceof ApiError) {
        if (error.code === 'ip_blocked') {
          status = { authorized: false, blocked: true, remainingAttempts: 0 };
        } else if (error.code === 'invalid_answer') {
          status = {
            authorized: false,
            blocked: false,
            remainingAttempts: Number(error.details.remainingAttempts ?? 0),
          };
          invalid = true;
        } else {
          serviceError = true;
        }
      } else {
        serviceError = true;
      }
    } finally {
      answer = '';
      submitting = false;
    }
  }
</script>

<main class="mx-auto flex min-h-[68vh] max-w-xl items-center px-4 py-10">
  <section class="w-full rounded-3xl border border-slate-200 bg-white p-6 shadow-xl shadow-slate-900/5 dark:border-zinc-800 dark:bg-zinc-900 dark:shadow-black/20" aria-labelledby="gate-title">
    <p class="text-xs font-bold uppercase tracking-[0.2em] text-violet-600 dark:text-violet-400">{$t('gate.kicker')}</p>
    <h1 id="gate-title" class="mt-2 text-3xl font-bold text-slate-950 dark:text-white">{status.blocked ? $t('gate.error.blocked_title') : $t('gate.title')}</h1>

    {#if status.blocked}
      <div class="mt-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-900 dark:border-red-900/70 dark:bg-red-950/40 dark:text-red-100" role="alert">
        {$t('gate.error.blocked')}
      </div>
    {:else if serviceError}
      <div class="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-950 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-100" role="alert">
        {$t('gate.error.service')}
      </div>
    {:else}
      <p class="mt-3 text-slate-600 dark:text-zinc-300">{$t('gate.intro')}</p>
      <form class="mt-6 space-y-4" on:submit|preventDefault={submit}>
        <div>
          <label class="block text-sm font-semibold text-slate-900 dark:text-zinc-100" for="gate-answer">{$t('gate.question')}</label>
          <input
            id="gate-answer"
            class="mt-2 w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-lg uppercase text-slate-950 shadow-sm dark:border-zinc-700 dark:bg-zinc-950 dark:text-white"
            bind:value={answer}
            maxlength="32"
            autocomplete="off"
            autocapitalize="characters"
            placeholder={$t('gate.placeholder')}
            aria-describedby="gate-feedback gate-privacy"
            disabled={submitting}
            required
          />
        </div>
        <div id="gate-feedback" class="min-h-6 text-sm" aria-live="polite">
          {#if invalid}<span class="font-semibold text-red-600 dark:text-red-400">{$t('gate.error.invalid')} {$t(status.remainingAttempts === 1 ? 'gate.remaining.one' : 'gate.remaining.other', { count: status.remainingAttempts })}</span>{/if}
        </div>
        <button class="w-full rounded-2xl bg-violet-600 px-5 py-3 font-bold text-white shadow-lg shadow-violet-600/20 transition hover:bg-violet-500 disabled:cursor-wait disabled:opacity-60" type="submit" disabled={submitting || !answer.trim()}>
          {submitting ? $t('gate.checking') : $t('gate.submit')}
        </button>
      </form>
    {/if}

    <p id="gate-privacy" class="mt-6 border-t border-slate-200 pt-4 text-xs leading-relaxed text-slate-500 dark:border-zinc-800 dark:text-zinc-400">{$t('gate.privacy')}</p>
  </section>
</main>
