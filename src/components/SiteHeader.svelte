<script lang="ts">
  import { dayNavigation } from '../lib/day-navigation';
  import { changeLanguage, language, languages, t } from '../lib/i18n';

  export let compact = false;
  let dark = document.documentElement.classList.contains('dark');
  let controllerDialog: HTMLDialogElement;

  function toggleTheme(): void {
    dark = !dark;
    document.documentElement.classList.toggle('dark', dark);
    try {
      localStorage.setItem('vplan-theme', dark ? 'dark' : 'light');
    } catch {
      // Theme changes still work for the current page.
    }
  }

  function formatDate(value: string): string {
    const parsed = new Date(`${value}T12:00:00`);
    return new Intl.DateTimeFormat($language, {
      weekday: 'long',
      day: '2-digit',
      month: 'long',
    }).format(parsed);
  }
</script>

<aside class="border-b border-slate-200/80 bg-white/70 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/70" aria-label={$t('utility.label')}>
  <div class="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4 py-2 text-xs text-slate-600 dark:text-zinc-400">
    <span>{$t('app.unofficial')}</span>
    <nav class="flex flex-wrap items-center justify-end gap-2" aria-label={$t('utility.label')}>
      <div class="flex items-center gap-1" role="group" aria-label={$t('language.label')}>
        {#each $languages as item (item.code)}
          <button
            type="button"
            class="rounded-full px-2 py-1 transition hover:bg-slate-100 dark:hover:bg-zinc-800"
            class:bg-violet-100={$language === item.code}
            class:dark:bg-violet-950={$language === item.code}
            aria-pressed={$language === item.code}
            aria-label={`${item.name}${item.status === 'beta' ? ` (${$t('translator.language_beta')})` : ''}`}
            on:click={() => changeLanguage(item.code)}
          >{item.flag}</button>
        {/each}
      </div>
      <span aria-hidden="true">·</span>
      <button class="hover:text-violet-600" type="button" on:click={() => controllerDialog.showModal()}>{$t('utility.controller')}</button>
      <span aria-hidden="true">·</span>
      <a class="hover:text-violet-600" href="/privacy">{$t('utility.privacy')}</a>
      <span aria-hidden="true">·</span>
      <a class="hover:text-violet-600" href="/credits">{$t('utility.credits')}</a>
      <span aria-hidden="true">·</span>
      <a
        class="hover:text-violet-600"
        href="https://github.com/EchterAlsFake/all4schools-substitution-viewer"
        target="_blank"
        rel="noopener noreferrer"
        aria-label={$t('utility.github_label')}
      >{$t('utility.github')}</a>
      <span aria-hidden="true">·</span>
      <a class="hover:text-violet-600" href="/changelog">{$t('utility.changelog')}</a>
      <span aria-hidden="true">·</span>
      <a class="hover:text-violet-600" href="/translate">{$t('utility.translate')}</a>
    </nav>
  </div>
</aside>

{#if !compact}
  <header class="border-b border-slate-200/80 bg-white/80 dark:border-zinc-800 dark:bg-zinc-950/80">
    <div class="mx-auto flex max-w-6xl flex-wrap items-center gap-3 px-4 py-4 md:flex-nowrap">
      <a class="order-1 flex min-w-0 flex-1 items-center gap-3 md:flex-none" href="/" aria-label={$t('app.title')}>
        <span class="grid size-11 shrink-0 place-items-center rounded-2xl bg-violet-600 text-xl text-white shadow-lg shadow-violet-600/20" aria-hidden="true">✓</span>
        <span class="min-w-0">
          <span class="block text-xs font-semibold uppercase tracking-[0.2em] text-violet-600 dark:text-violet-400">{$t('app.eyebrow')}</span>
          <span class="block truncate text-xl font-bold text-slate-950 dark:text-white sm:text-2xl">{$t('app.title')}</span>
        </span>
      </a>

      {#if $dayNavigation.items.length}
        <nav class="order-3 min-w-0 basis-full overflow-x-auto pt-1 md:order-2 md:basis-auto md:flex-1 md:px-2 md:pt-0" aria-label={$t('navigation.choose_day')}>
          <div class="flex min-w-max gap-2 md:justify-center">
            {#each $dayNavigation.items as day (day.date)}
              <button
                type="button"
                class="min-w-fit rounded-xl border px-3 py-2 text-left text-sm transition"
                class:border-violet-500={$dayNavigation.activeDate === day.date}
                class:bg-violet-600={$dayNavigation.activeDate === day.date}
                class:text-white={$dayNavigation.activeDate === day.date}
                class:border-slate-200={$dayNavigation.activeDate !== day.date}
                class:bg-white={$dayNavigation.activeDate !== day.date}
                class:dark:border-zinc-700={$dayNavigation.activeDate !== day.date}
                class:dark:bg-zinc-900={$dayNavigation.activeDate !== day.date}
                aria-pressed={$dayNavigation.activeDate === day.date}
                on:click={() => $dayNavigation.selectDay(day.date)}
              >
                <strong class="block whitespace-nowrap capitalize">{formatDate(day.date)}</strong>
                <small class="block whitespace-nowrap">{$t(day.entryCount === 1 ? 'plan.change.one' : 'plan.change.other', { count: day.entryCount })}</small>
              </button>
            {/each}
          </div>
        </nav>
      {/if}

      <button
        type="button"
        class="order-2 ml-auto grid size-11 shrink-0 place-items-center rounded-2xl border border-slate-200 bg-white text-xl shadow-sm transition hover:border-violet-400 dark:border-zinc-700 dark:bg-zinc-900 md:order-3 md:ml-0"
        aria-label={dark ? $t('theme.enable_light') : $t('theme.enable_dark')}
        title={$t('theme.switch')}
        on:click={toggleTheme}
      >
        <span aria-hidden="true">{dark ? '☀' : '☾'}</span>
      </button>
    </div>
  </header>
{/if}

<dialog bind:this={controllerDialog} class="m-auto w-[calc(100%-2rem)] max-w-lg rounded-3xl bg-white p-0 text-slate-950 shadow-2xl dark:bg-zinc-900 dark:text-white" aria-labelledby="controller-title">
  <div class="p-6 sm:p-8">
    <div class="flex items-start justify-between gap-4">
      <div>
        <p class="text-xs font-bold uppercase tracking-[0.2em] text-violet-600 dark:text-violet-400">{$t('info.controller.kicker')}</p>
        <h2 id="controller-title" class="mt-1 text-2xl font-bold">{$t('info.controller.title')}</h2>
      </div>
      <button type="button" class="rounded-xl px-3 py-2" aria-label={$t('common.dialog_close')} on:click={() => controllerDialog.close()}>×</button>
    </div>
    <address class="mt-5 not-italic leading-relaxed text-slate-700 dark:text-zinc-300">
      <strong>{$t('controller.name')}</strong><br />
      {$t('controller.street')}<br />
      {$t('controller.city')}<br />
      {$t('controller.country')}
    </address>
    <p class="mt-4 leading-relaxed text-slate-700 dark:text-zinc-300">
      <span>{$t('info.controller.email')}</span>
      <a class="text-violet-600 underline dark:text-violet-400" href="mailto:echteralsfakebs@proton.me">{$t('controller.email_value')}</a><br />
      <span>{$t('info.controller.phone')}</span>
      <a class="text-violet-600 underline dark:text-violet-400" href="tel:+491744646064">{$t('controller.phone_value')}</a>
    </p>
    <p class="mt-4 text-sm leading-relaxed text-slate-600 dark:text-zinc-300">{$t('info.controller.disclaimer')}</p>
    <a class="mt-5 inline-flex rounded-xl bg-violet-600 px-4 py-2 font-bold text-white" href="/imprint">{$t('info.controller.full_link')}</a>
  </div>
</dialog>
