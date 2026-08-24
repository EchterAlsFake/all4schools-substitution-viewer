<script lang="ts">
  import { onMount } from 'svelte';

  import Gate from './components/Gate.svelte';
  import InfoPage from './components/InfoPage.svelte';
  import LegalPage from './components/LegalPage.svelte';
  import PlanApp from './components/PlanApp.svelte';
  import SiteHeader from './components/SiteHeader.svelte';
  import TranslatorPage from './components/TranslatorPage.svelte';
  import { restoreStoredAccess } from './lib/access';
  import { ApiError, getAuthStatus, logout } from './lib/api';
  import { i18nReady, initializeI18n, t } from './lib/i18n';
  import { forgetGateAnswer } from './lib/storage';
  import type { AuthStatus } from './lib/types';

  const route = window.location.pathname.replace(/\/+$/, '') || '/';
  let auth: AuthStatus | null = null;
  let authServiceError = false;

  onMount(async () => {
    try {
      await initializeI18n();
    } catch {
      // The German key fallback still leaves the page operable.
      i18nReady.set(true);
    }
    if (route === '/') await refreshAuth();
  });

  async function refreshAuth(): Promise<void> {
    try {
      auth = await restoreStoredAccess(await getAuthStatus());
      authServiceError = false;
    } catch (error) {
      authServiceError = true;
      auth = {
        authorized: false,
        blocked: error instanceof ApiError && error.code === 'ip_blocked',
        remainingAttempts: 0,
      };
    }
  }

  async function resetAccess(): Promise<void> {
    forgetGateAnswer();
    await logout().catch(() => undefined);
    window.location.reload();
  }
</script>

<svelte:head>
  <meta name="color-scheme" content="light dark" />
</svelte:head>

<a class="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-white focus:p-3 focus:text-slate-950" href="#plan-content">{$t('app.skip')}</a>
<SiteHeader compact={route !== '/'} />

{#if !$i18nReady}
  <main class="mx-auto grid max-w-xl place-items-center px-4 py-20" aria-busy="true">
    <span class="size-8 animate-spin rounded-full border-4 border-slate-200 border-t-violet-600 dark:border-zinc-700 dark:border-t-violet-400" aria-hidden="true"></span>
  </main>
{:else if route === '/privacy'}
  <LegalPage page="privacy" />
{:else if route === '/imprint'}
  <LegalPage page="imprint" />
{:else if route === '/translate'}
  <TranslatorPage />
{:else if route === '/credits'}
  <InfoPage page="credits" />
{:else if route === '/changelog'}
  <InfoPage page="changelog" />
{:else if route !== '/'}
  <main class="mx-auto max-w-xl px-4 py-20 text-center"><h1 class="text-3xl font-bold">404</h1><a class="mt-5 inline-block text-violet-600 underline" href="/">{$t('common.back')}</a></main>
{:else if auth?.authorized}
  <PlanApp />
  <div class="mx-auto max-w-6xl px-4 pb-6 text-center"><button type="button" class="text-xs text-slate-500 underline dark:text-zinc-400" on:click={resetAccess}>{$t('auth.logout')}</button></div>
{:else if auth}
  <Gate status={auth} serviceError={authServiceError} onAuthorized={() => { auth = { authorized: true, blocked: false, remainingAttempts: 3 }; }} />
{:else}
  <main class="mx-auto max-w-xl px-4 py-20 text-center" role="status">{$t('state.loading')}</main>
{/if}

<footer class="border-t border-slate-200 px-4 py-6 text-center text-xs text-slate-500 dark:border-zinc-800 dark:text-zinc-400">{$t('app.footer')}</footer>
