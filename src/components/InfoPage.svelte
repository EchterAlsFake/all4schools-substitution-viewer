<script lang="ts">
  import { t } from '../lib/i18n';

  export let page: 'credits' | 'changelog';
</script>

<main class="mx-auto max-w-3xl px-4 py-8">
  <a class="inline-flex rounded-xl px-3 py-2 font-semibold text-violet-600 hover:bg-violet-50 dark:text-violet-400 dark:hover:bg-violet-950/40" href="/">{$t('legal.back')}</a>
  <article class="mt-4 space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-9">
    {#if page === 'credits'}
      <header><p class="text-xs font-bold uppercase tracking-[0.2em] text-violet-600">{$t('credits.kicker')}</p><h1 class="mt-2 text-3xl font-bold">{$t('utility.credits')}</h1></header>
      <section class="grid gap-3 sm:grid-cols-2">
        <div class="rounded-2xl bg-slate-100 p-4 dark:bg-zinc-800"><h2 class="font-bold">{$t('credits.tech')}</h2><p class="mt-1 text-sm">{$t('credits.stack')}</p></div>
        <div class="rounded-2xl bg-slate-100 p-4 dark:bg-zinc-800"><h2 class="font-bold">{$t('credits.programming')}</h2><p class="mt-1 text-sm">{$t('credits.programming_value')}</p></div>
        <div class="rounded-2xl bg-slate-100 p-4 dark:bg-zinc-800"><h2 class="font-bold">{$t('credits.hosting')}</h2><p class="mt-1 text-sm">{$t('credits.hosting_value')}</p></div>
        <div class="rounded-2xl bg-slate-100 p-4 dark:bg-zinc-800"><h2 class="font-bold">{$t('credits.code')}</h2><p class="mt-1 text-sm">{$t('credits.code_value')}</p></div>
      </section>
      <section><h2 class="text-xl font-bold">{$t('credits.thanks')}</h2><ul class="mt-3 list-inside list-disc space-y-2 text-slate-700 dark:text-zinc-300"><li>{$t('credits.rename')}: {$t('credits.rename_value')}</li><li>{$t('credits.install')}: {$t('credits.install_value')}</li></ul></section>
    {:else}
      <header><p class="text-xs font-bold uppercase tracking-[0.2em] text-violet-600">{$t('changelog.kicker')}</p><h1 class="mt-2 text-3xl font-bold">{$t('changelog.title')}</h1><p class="mt-3 text-slate-600 dark:text-zinc-300">{$t('changelog.intro')}</p></header>
      <section class="rounded-2xl border border-violet-200 bg-violet-50 p-5 dark:border-violet-900 dark:bg-violet-950/30"><p class="text-xs font-bold uppercase tracking-widest text-violet-600">{$t('changelog.current')}</p><h2 class="mt-2 text-xl font-bold">{$t('changelog.rebuild.title')}</h2><ul class="mt-3 list-inside list-disc space-y-2 text-sm leading-relaxed"><li>{$t('changelog.rebuild.item_1')}</li><li>{$t('changelog.rebuild.item_2')}</li><li>{$t('changelog.rebuild.item_3')}</li><li>{$t('changelog.rebuild.item_4')}</li></ul></section>
      {#each [['changelog.quality.title','changelog.quality.item_2'],['changelog.colors.title','changelog.colors.text'],['changelog.personal.title','changelog.personal.item_2']] as item (item[0])}<section class="rounded-2xl bg-slate-100 p-5 dark:bg-zinc-800"><h2 class="font-bold">{$t(item[0])}</h2><p class="mt-2 text-sm leading-relaxed">{$t(item[1])}</p></section>{/each}
    {/if}
  </article>
</main>
