<script lang="ts">
  import { t } from '../lib/i18n';

  type Catalog = Record<string, string | boolean>;
  let source: Catalog = {};
  let target: Catalog = { _meta: false };
  let code = 'uk';
  let name = '';
  let search = '';
  let missingOnly = false;
  let status = '';

  $: keys = Object.keys(source).filter((key) => key !== '_meta' && typeof source[key] === 'string');
  $: filtered = keys.filter((key) => {
    const value = String(source[key]);
    const matches = `${key} ${value}`.toLocaleLowerCase().includes(search.toLocaleLowerCase());
    return matches && (!missingOnly || !String(target[key] || '').trim());
  });
  $: translated = keys.filter((key) => String(target[key] || '').trim()).length;

  fetch('/i18n/de.json', { credentials: 'omit', referrerPolicy: 'no-referrer' })
    .then((response) => response.json())
    .then((catalog: Catalog) => (source = catalog))
    .catch(() => (status = 'translator.status.source_error'));

  function placeholders(value: string): string[] {
    return [...value.matchAll(/\{([A-Za-z0-9_]+)\}/g)].map((match) => match[1]).sort();
  }

  function validate(): boolean {
    if (!/^[a-z]{2,8}(?:-[a-z0-9]{2,8})*$/i.test(code) || code.toLowerCase() === 'de') {
      status = 'translator.status.invalid_code';
      return false;
    }
    if (!name.trim()) {
      status = 'translator.status.name_required';
      return false;
    }
    const invalid = keys.some((key) => {
      const value = String(target[key] || '');
      return /<[^>]+>/.test(value) || placeholders(value).join(',') !== placeholders(String(source[key])).join(',');
    });
    if (invalid) {
      status = 'translator.status.invalid_rows';
      return false;
    }
    status = translated === keys.length ? 'translator.status.valid_complete' : 'translator.status.valid_missing';
    return true;
  }

  async function importCatalog(event: Event): Promise<void> {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    try {
      const imported = JSON.parse(await file.text()) as Catalog;
      target = Object.fromEntries(Object.entries(imported).filter(([, value]) => typeof value === 'string'));
      status = 'translator.status.imported';
    } catch {
      status = 'translator.status.import_error';
    }
  }

  function download(): void {
    if (!validate()) return;
    const output: Catalog = {
      ...Object.fromEntries(keys.map((key) => [key, String(target[key] || '')])),
    };
    const metadata = { code: code.toLowerCase(), name: name.trim(), source: false, reviewed: false };
    const blob = new Blob([`${JSON.stringify({ _meta: metadata, ...output }, null, 2)}\n`], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${code.toLowerCase()}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }
</script>

<main class="mx-auto max-w-5xl px-4 py-8">
  <a class="inline-flex rounded-xl px-3 py-2 font-semibold text-violet-600 hover:bg-violet-50 dark:text-violet-400 dark:hover:bg-violet-950/40" href="/">{$t('legal.back')}</a>
  <section class="mt-4 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-8">
    <p class="text-xs font-bold uppercase tracking-[0.2em] text-violet-600 dark:text-violet-400">{$t('translator.eyebrow')}</p>
    <h1 class="mt-2 text-3xl font-bold">{$t('translator.title')}</h1>
    <p class="mt-3 text-slate-600 dark:text-zinc-300">{$t('translator.intro')}</p>
    <div class="mt-6 grid gap-4 sm:grid-cols-2">
      <label class="font-semibold">{$t('translator.language_code')}<input class="mt-2 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-zinc-700" bind:value={code} maxlength="24" placeholder={$t('translator.language_code_placeholder')} /></label>
      <label class="font-semibold">{$t('translator.language_name')}<input class="mt-2 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-zinc-700" bind:value={name} maxlength="80" placeholder={$t('translator.language_name_placeholder')} /></label>
      <label class="font-semibold sm:col-span-2">{$t('translator.import')}<input class="mt-2 block w-full text-sm" type="file" accept="application/json,.json" on:change={importCatalog} /></label>
    </div>
    <div class="mt-8 flex flex-wrap items-end gap-3">
      <label class="min-w-56 flex-1 font-semibold">{$t('translator.search_label')}<input class="mt-2 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-zinc-700" bind:value={search} placeholder={$t('translator.search_placeholder')} /></label>
      <label class="flex items-center gap-2 rounded-xl border border-slate-300 px-3 py-2 dark:border-zinc-700"><input type="checkbox" bind:checked={missingOnly} /> {$t('translator.missing_only')}</label>
    </div>
    <p class="mt-4 text-sm text-slate-500">{$t('translator.progress', { translated, total: keys.length })}</p>
    <div class="mt-4 max-h-[55vh] space-y-3 overflow-y-auto pr-1">
      {#each filtered as key (key)}
        <label class="block rounded-2xl border border-slate-200 p-4 dark:border-zinc-700">
          <span class="block text-xs font-mono text-violet-600 dark:text-violet-400">{key}</span>
          <span class="mt-1 block text-sm text-slate-600 dark:text-zinc-300">{source[key]}</span>
          <textarea class="mt-3 min-h-20 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-zinc-600" value={String(target[key] || '')} on:input={(event) => { target = { ...target, [key]: (event.currentTarget as HTMLTextAreaElement).value }; }} aria-label={`${$t('translator.translation_label')}: ${key}`}></textarea>
        </label>
      {:else}
        <p class="rounded-2xl bg-slate-100 p-4 dark:bg-zinc-800">{$t('translator.no_results')}</p>
      {/each}
    </div>
    {#if status}<p class="mt-4 font-semibold" role="status">{$t(status, { count: keys.length - translated, name })}</p>{/if}
    <div class="mt-6 flex flex-wrap gap-3">
      <button type="button" class="rounded-xl border border-violet-500 px-4 py-2 font-bold text-violet-600 dark:text-violet-400" on:click={validate}>{$t('translator.validate')}</button>
      <button type="button" class="rounded-xl bg-violet-600 px-4 py-2 font-bold text-white" on:click={download}>{$t('translator.download')}</button>
    </div>
  </section>
</main>
