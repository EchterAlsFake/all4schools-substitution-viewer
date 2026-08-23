<script lang="ts">
  import { t } from '../lib/i18n';

  export let page: 'privacy' | 'imprint';
</script>

<main class="mx-auto max-w-3xl px-4 py-8">
  <a class="inline-flex rounded-xl px-3 py-2 font-semibold text-violet-600 hover:bg-violet-50 dark:text-violet-400 dark:hover:bg-violet-950/40" href="/">{$t('legal.back')}</a>
  <article class="mt-4 space-y-7 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-9">
    <header>
      <p class="text-xs font-bold uppercase tracking-[0.2em] text-violet-600 dark:text-violet-400">{$t(page === 'privacy' ? 'app.unofficial' : 'info.controller.kicker')}</p>
      <h1 class="mt-2 text-3xl font-bold text-slate-950 dark:text-white">{$t(page === 'privacy' ? 'legal.privacy_heading' : 'legal.imprint_heading')}</h1>
      {#if page === 'privacy'}<p class="mt-2 text-sm text-slate-500 dark:text-zinc-400">{$t('legal.updated')}</p>{/if}
    </header>

    <section>
      <h2 class="text-xl font-bold">{$t('info.controller.title')}</h2>
      <address class="mt-2 not-italic leading-relaxed text-slate-700 dark:text-zinc-300">
        <strong>{$t('controller.name')}</strong><br />
        {$t('controller.street')}<br />
        {$t('controller.city')}<br />
        {$t('controller.country')}
      </address>
      <p class="mt-3"><a class="text-violet-600 underline dark:text-violet-400" href="mailto:echteralsfakebs@proton.me">{$t('controller.email_value')}</a></p>
    </section>

    {#if page === 'privacy'}
      {#each [
        ['privacy.no_tracking.title', 'privacy.no_tracking.text'],
        ['legal.access_title', 'legal.access_text'],
        ['privacy.plan_requests.title', 'privacy.plan_requests.text'],
        ['privacy.local.title', 'privacy.local.text'],
        ['privacy.redaction.title', 'privacy.redaction.text'],
        ['privacy.feedback.title', 'privacy.feedback.text'],
        ['privacy.cloudflare.title', 'privacy.cloudflare.text'],
        ['privacy.github.title', 'privacy.github.text'],
        ['privacy.rights.title', 'privacy.rights.text'],
      ] as section (section[0])}
        <section>
          <h2 class="text-xl font-bold">{$t(section[0])}</h2>
          <p class="mt-2 leading-relaxed text-slate-700 dark:text-zinc-300">{$t(section[1])}</p>
          {#if section[0] === 'privacy.cloudflare.title'}
            <p class="mt-3 leading-relaxed text-slate-700 dark:text-zinc-300">{$t('privacy.cloudflare.transfer')}</p>
            <a class="mt-3 inline-block text-violet-600 underline dark:text-violet-400" href="https://www.cloudflare.com/privacypolicy/" target="_blank" rel="noopener noreferrer">{$t('privacy.cloudflare_link')}</a>
          {/if}
        </section>
      {/each}
      <p class="leading-relaxed text-slate-700 dark:text-zinc-300">{$t('legal.privacy_contact')}</p>
    {:else}
      <section>
        <h2 class="text-xl font-bold">{$t('info.controller.contact')}</h2>
        <p class="mt-2 leading-relaxed"><span>{$t('info.controller.email')}</span> <a class="text-violet-600 underline dark:text-violet-400" href="mailto:echteralsfakebs@proton.me">{$t('controller.email_value')}</a><br />
          <span>{$t('info.controller.phone')}</span> <a class="text-violet-600 underline dark:text-violet-400" href="tel:+491744646064">{$t('controller.phone_value')}</a></p>
      </section>
      <section>
        <h2 class="text-xl font-bold">{$t('legal.disclaimer_title')}</h2>
        <p class="mt-2 leading-relaxed text-slate-700 dark:text-zinc-300">{$t('disclaimer.unofficial.text')}</p>
        <p class="mt-3 leading-relaxed text-slate-700 dark:text-zinc-300">{$t('legal.disclaimer_text')}</p>
      </section>
    {/if}
  </article>
</main>
