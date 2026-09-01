<script lang="ts">
  import { onDestroy, onMount } from 'svelte';

  import { ApiError, getPlan, sendFeedback } from '../lib/api';
  import { clearDayNavigation, dayNavigation } from '../lib/day-navigation';
  import { language, t } from '../lib/i18n';
  import { sortEntriesByClass } from '../lib/plan-sort';
  import { isPlanRefreshWindow, PLAN_REFRESH_INTERVAL_MS } from '../lib/refresh-schedule';
  import {
    defaultPreferences,
    loadOverrides,
    loadPreferences,
    readStorage,
    TRANSPARENCY_NOTICE_STORAGE_KEY,
    writeStorage,
  } from '../lib/storage';
  import type {
    PlanDay,
    PlanEntry,
    PlanResponse,
    Preferences,
    SubjectOverride,
    SubjectOverrides,
  } from '../lib/types';

  let plan: PlanResponse | null = null;
  let loading = true;
  let loadError = false;
  let activeDate = '';
  let search = '';
  let cancelledOnly = false;
  let preferences: Preferences = loadPreferences();
  let overrides: SubjectOverrides = loadOverrides();
  let settingsDialog: HTMLDialogElement;
  let feedbackDialog: HTMLDialogElement;
  let subjectDialog: HTMLDialogElement;
  let disclaimerDialog: HTMLDialogElement;
  let transparencyDialog: HTMLDialogElement;
  let feedbackMessage = '';
  let feedbackConfirmed = false;
  let feedbackStatus = '';
  let feedbackSending = false;
  let disclaimerConfirmed = false;
  let customCourses = '';
  let editingEntry: PlanEntry | null = null;
  let editingOverride: SubjectOverride = { name: '', teacher: '', color: '' };
  let installStatus = '';
  let storageNotice = '';
  let transparencyNoticeSeen = readStorage<unknown>(TRANSPARENCY_NOTICE_STORAGE_KEY, false) === true;

  const colors: Record<string, string> = {
    violet: 'border-violet-500 bg-violet-50/70 dark:bg-violet-950/25',
    blue: 'border-blue-500 bg-blue-50/70 dark:bg-blue-950/25',
    cyan: 'border-cyan-500 bg-cyan-50/70 dark:bg-cyan-950/25',
    green: 'border-green-500 bg-green-50/70 dark:bg-green-950/25',
    lime: 'border-lime-500 bg-lime-50/70 dark:bg-lime-950/25',
    amber: 'border-amber-500 bg-amber-50/70 dark:bg-amber-950/25',
    orange: 'border-orange-500 bg-orange-50/70 dark:bg-orange-950/25',
    pink: 'border-pink-500 bg-pink-50/70 dark:bg-pink-950/25',
  };

  const colorSwatches: Record<string, string> = {
    violet: 'bg-violet-500',
    blue: 'bg-blue-500',
    cyan: 'bg-cyan-500',
    green: 'bg-green-500',
    lime: 'bg-lime-500',
    amber: 'bg-amber-500',
    orange: 'bg-orange-500',
    pink: 'bg-pink-500',
  };

  $: activeDay = plan?.days.find((day) => day.date === activeDate) ?? plan?.days[0] ?? null;
  $: courseCodes = [...new Set([
    ...(plan?.learnedCourseCodes ?? []),
    ...(plan?.days.flatMap((day) => day.entries.flatMap((entry) => entry.classes)) ?? []),
  ])].sort((a, b) => a.localeCompare(b, 'de', { numeric: true }));
  $: gradeCourses = courseCodes.filter((code) => {
    const match = code.match(/^0?(\d{1,2})/);
    return match?.[1] === preferences.grade && !/^0?\d{1,2}[abc]$/i.test(code);
  });
  $: visibleEntries = sortEntriesByClass(
    (activeDay?.entries ?? []).filter((entry) =>
      matchesPersonalPlan(entry) &&
      (!cancelledOnly || entry.kind === 'cancelled') &&
      matchesSearch(entry),
    ),
  );
  $: dayNavigation.set({
    items: (plan?.days ?? []).map((day) => ({ date: day.date, entryCount: day.entries.length })),
    activeDate,
    selectDay,
  });

  onMount(() => {
    queueMicrotask(showInitialNotice);
    void refreshPlan();
    const refreshTimer = window.setInterval(() => {
      if (isPlanRefreshWindow()) void refreshPlan(true);
    }, PLAN_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(refreshTimer);
  });

  onDestroy(() => clearDayNavigation(selectDay));

  async function refreshPlan(silent = false): Promise<void> {
    if (!silent) loading = true;
    try {
      const nextPlan = await getPlan();
      const previousVersion = plan?.version;
      plan = nextPlan;
      loadError = false;
      if (!activeDate || !nextPlan.days.some((day) => day.date === activeDate)) {
        activeDate = defaultDate(nextPlan.days);
      } else if (previousVersion === nextPlan.version) {
        // Keep the manually selected tab when content did not change.
      }
      queueMicrotask(showInitialNotice);
    } catch (error) {
      loadError = true;
      if (error instanceof ApiError && ['authentication_required', 'ip_blocked'].includes(error.code)) {
        window.location.reload();
      }
    } finally {
      loading = false;
    }
  }

  function defaultDate(days: PlanDay[]): string {
    if (!days.length) return '';
    const local = new Date();
    const today = [local.getFullYear(), String(local.getMonth() + 1).padStart(2, '0'), String(local.getDate()).padStart(2, '0')].join('-');
    const sorted = days.map((day) => day.date).sort();
    if (local.getHours() < 15 && sorted.includes(today)) return today;
    return sorted.find((day) => day > today) || (sorted.includes(today) ? today : sorted[sorted.length - 1]);
  }

  function selectDay(date: string): void {
    if (plan?.days.some((day) => day.date === date)) activeDate = date;
  }

  function normalizedCode(value: string): string {
    return value.trim().toLocaleLowerCase().replace(/^0(?=\d)/, '');
  }

  function matchesPersonalPlan(entry: PlanEntry): boolean {
    if (!preferences.enabled || !preferences.grade) return true;
    const codes = entry.classes.map(normalizedCode);
    const selectedCourses = preferences.courses.map(normalizedCode);
    const grade = Number(preferences.grade);
    if (grade <= 10) {
      const baseClass = `${grade}${preferences.classLetter.toLocaleLowerCase()}`;
      return codes.includes(baseClass) || codes.some((code) => selectedCourses.includes(code));
    }
    return codes.some((code) => selectedCourses.includes(code));
  }

  function matchesSearch(entry: PlanEntry): boolean {
    const needle = search.trim().toLocaleLowerCase();
    if (!needle) return true;
    const override = overrides[overrideKey(entry)];
    return [
      entry.oldSubject,
      entry.newSubject,
      entry.comment,
      ...entry.classes,
      ...entry.oldRooms,
      ...entry.newRooms,
      override?.name,
      override?.teacher,
    ].some((value) => String(value || '').toLocaleLowerCase().includes(needle));
  }

  function overrideKey(entry: PlanEntry): string {
    return `${normalizedCode(entry.classes[0] || 'unknown')}::${normalizedCode(entry.oldSubject || entry.newSubject || 'subject')}`;
  }

  function formatTime(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.valueOf())
      ? $t('entry.time_unknown')
      : new Intl.DateTimeFormat($language, { hour: '2-digit', minute: '2-digit' }).format(parsed);
  }

  function kindLabel(entry: PlanEntry): string {
    return $t(
      entry.kind === 'cancelled'
        ? 'entry.cancelled'
        : entry.kind === 'self_study'
          ? 'entry.self_study'
          : entry.kind === 'unknown'
            ? 'entry.unknown'
            : 'entry.changed',
    );
  }

  function openSettings(): void {
    customCourses = preferences.courses.filter((course) => !courseCodes.includes(course)).join(', ');
    settingsDialog.showModal();
  }

  function toggleCourse(code: string, checked: boolean): void {
    preferences = {
      ...preferences,
      courses: checked
        ? [...new Set([...preferences.courses, code])]
        : preferences.courses.filter((course) => course !== code),
    };
  }

  function savePreferences(): void {
    const custom = customCourses.split(',').map((code) => code.trim()).filter(Boolean).slice(0, 50);
    preferences = {
      ...preferences,
      classLetter: preferences.classLetter.toLocaleLowerCase(),
      courses: [...new Set([...preferences.courses, ...custom])].slice(0, 100),
    };
    if (!writeStorage('vplan-preferences', preferences)) storageNotice = $t('settings.error.storage');
    settingsDialog.close();
  }

  function resetPreferences(): void {
    preferences = { ...defaultPreferences };
    if (!writeStorage('vplan-preferences', preferences)) storageNotice = $t('settings.error.delete');
    settingsDialog.close();
  }

  function openSubject(entry: PlanEntry): void {
    editingEntry = entry;
    editingOverride = { ...(overrides[overrideKey(entry)] || { name: '', teacher: '', color: '' }) };
    subjectDialog.showModal();
  }

  function saveSubject(): void {
    if (!editingEntry) return;
    editingOverride = {
      name: editingOverride.name.trim().slice(0, 60),
      teacher: editingOverride.teacher.trim().slice(0, 60),
      color: Object.hasOwn(colors, editingOverride.color) ? editingOverride.color : '',
    };
    overrides = { ...overrides, [overrideKey(editingEntry)]: editingOverride };
    if (!writeStorage('vplan-subject-overrides', overrides)) storageNotice = $t('subject.storage_error');
    subjectDialog.close();
  }

  function resetSubject(): void {
    if (!editingEntry) return;
    const next = { ...overrides };
    delete next[overrideKey(editingEntry)];
    overrides = next;
    if (!writeStorage('vplan-subject-overrides', overrides)) storageNotice = $t('subject.delete_error');
    subjectDialog.close();
  }

  async function submitFeedback(): Promise<void> {
    if (feedbackMessage.trim().length < 10) {
      feedbackStatus = 'feedback.error.too_short';
      return;
    }
    if (!feedbackConfirmed) {
      feedbackStatus = 'feedback.error.confirm';
      return;
    }
    feedbackSending = true;
    try {
      await sendFeedback(feedbackMessage);
      feedbackStatus = 'feedback.success';
      feedbackMessage = '';
      feedbackConfirmed = false;
    } catch (error) {
      const code = error instanceof ApiError ? error.code : 'save';
      const mapping: Record<string, string> = {
        html_not_allowed: 'feedback.error.html',
        contact_data_not_allowed: 'feedback.error.contact',
        privacy_confirmation_required: 'feedback.error.confirm',
        rate_limited: 'feedback.error.rate_limited',
      };
      feedbackStatus = mapping[code] || 'feedback.error.save';
    } finally {
      feedbackSending = false;
    }
  }

  function acceptDisclaimer(): void {
    if (!disclaimerConfirmed) return;
    if (!writeStorage('vplan-disclaimer-accepted-v1', true)) storageNotice = $t('storage.unavailable');
    disclaimerDialog.close();
  }

  function showInitialNotice(): void {
    if (!transparencyNoticeSeen) {
      if (!transparencyDialog) return;
      transparencyDialog.showModal();
      transparencyNoticeSeen = true;
      if (!writeStorage(TRANSPARENCY_NOTICE_STORAGE_KEY, true)) {
        storageNotice = $t('storage.unavailable');
      }
      return;
    }
    showDisclaimer();
  }

  function showDisclaimer(): void {
    if (
      !transparencyDialog?.open
      && !readStorage('vplan-disclaimer-accepted-v1', false)
      && !disclaimerDialog?.open
    ) {
      disclaimerDialog?.showModal();
    }
  }

  async function installApp(): Promise<void> {
    if (window.deferredInstallPrompt) {
      await window.deferredInstallPrompt.prompt();
      const result = await window.deferredInstallPrompt.userChoice;
      installStatus = result.outcome === 'accepted' ? 'install.installed' : 'install.fallback_intro';
      window.deferredInstallPrompt = undefined;
    } else {
      installStatus = 'install.fallback_intro';
    }
  }
</script>

<main id="plan-content" class="mx-auto max-w-6xl px-4 py-6" tabindex="-1">
  {#if storageNotice}<p class="mb-4 rounded-xl bg-amber-100 p-3 text-sm text-amber-950 dark:bg-amber-950/50 dark:text-amber-100" role="status">{storageNotice}</p>{/if}
  {#if plan?.stale}<p class="mb-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100" role="status">{$t('sync.stale')}</p>{/if}

  <section class="grid grid-cols-3 gap-2" aria-label={$t('quick.label')}>
    <button type="button" class="rounded-2xl border border-slate-200 bg-white p-3 text-left shadow-sm dark:border-zinc-800 dark:bg-zinc-900" on:click={openSettings}>
      <span class="text-xl" aria-hidden="true">◎</span><strong class="mt-2 block text-sm">{$t('quick.personal.title')}</strong><small class="hidden text-slate-500 sm:block">{$t('quick.personal.description')}</small>
    </button>
    <button type="button" class="rounded-2xl border border-slate-200 bg-white p-3 text-left shadow-sm dark:border-zinc-800 dark:bg-zinc-900" on:click={installApp}>
      <span class="text-xl" aria-hidden="true">↓</span><strong class="mt-2 block text-sm">{$t('quick.install.title')}</strong><small class="hidden text-slate-500 sm:block">{$t(installStatus || 'quick.install.description')}</small>
    </button>
    <button type="button" class="rounded-2xl border border-slate-200 bg-white p-3 text-left shadow-sm dark:border-zinc-800 dark:bg-zinc-900" on:click={() => feedbackDialog.showModal()}>
      <span class="text-xl" aria-hidden="true">!</span><strong class="mt-2 block text-sm">{$t('quick.feedback.title')}</strong><small class="hidden text-slate-500 sm:block">{$t('quick.feedback.description')}</small>
    </button>
  </section>

  <section class="mt-6 rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-6">
    <div class="flex flex-col gap-3 md:flex-row md:items-center">
      <div class="shrink-0">
        <p class="text-xs font-bold uppercase tracking-[0.2em] text-violet-600 dark:text-violet-400">{$t('changes.kicker')}</p>
        <h2 class="mt-1 text-2xl font-bold">{$t('changes.title')}</h2>
      </div>
      <label class="min-w-0 flex-1 text-sm font-semibold md:ml-2 md:max-w-md"><span class="sr-only">{$t('changes.search_label')}</span><input class="w-full rounded-xl border border-slate-300 bg-transparent px-4 py-2.5 dark:border-zinc-700" type="search" bind:value={search} placeholder={$t('changes.search_placeholder')} /></label>
      <label class="flex shrink-0 items-center gap-2 rounded-xl border border-slate-300 px-3 py-2.5 text-sm font-semibold dark:border-zinc-700"><input type="checkbox" bind:checked={cancelledOnly} /> {$t('changes.cancelled_only')}</label>
    </div>

    {#if loading}
      <p class="mt-6 rounded-2xl bg-slate-100 p-5 dark:bg-zinc-800" role="status">{$t('state.loading')}</p>
    {:else if loadError && !plan}
      <div class="mt-6 rounded-2xl bg-red-50 p-5 text-red-900 dark:bg-red-950/40 dark:text-red-100"><h3 class="font-bold">{$t('state.unavailable.title')}</h3><p class="mt-1">{$t('state.unavailable.description')}</p><button type="button" class="mt-4 rounded-xl bg-red-700 px-4 py-2 font-bold text-white" on:click={() => refreshPlan()}>{$t('sync.refresh')}</button></div>
    {:else if !activeDay}
      <div class="mt-6 rounded-2xl bg-slate-100 p-5 dark:bg-zinc-800"><h3 class="font-bold">{$t('state.empty.title')}</h3><p class="mt-1">{$t('state.empty.description')}</p></div>
    {:else if !visibleEntries.length}
      <div class="mt-6 rounded-2xl bg-slate-100 p-5 dark:bg-zinc-800"><h3 class="font-bold">{$t('results.none.title')}</h3><p class="mt-1">{$t('results.none.description')}</p></div>
    {:else}
      <div class="plan-entry-grid mt-5">
        {#each visibleEntries as entry (entry.id)}
          {@const local = overrides[overrideKey(entry)]}
          {@const displayName = local?.name || entry.newSubject || entry.oldSubject || $t('entry.no_description')}
          {@const rooms = entry.newRooms.length ? entry.newRooms : entry.oldRooms}
          <article class={`plan-entry-card rounded-2xl border-l-4 border-y border-r p-4 shadow-sm ${colors[local?.color] || 'border-slate-300 bg-slate-50/70 dark:border-zinc-700 dark:bg-zinc-950/40'}`}>
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2"><span class={`rounded-full px-2.5 py-1 text-xs font-bold ${entry.kind === 'cancelled' ? 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200' : 'bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-200'}`}>{kindLabel(entry)}</span>{#each entry.classes as code (code)}<span class="rounded-full bg-slate-200 px-2.5 py-1 text-xs font-semibold dark:bg-zinc-800">{code}</span>{/each}</div>
                <h3 class="mt-3 text-xl font-bold">{displayName}</h3>
                {#if local?.name}<p class="mt-1 text-xs text-slate-500">{$t('entry.original', { name: entry.newSubject || entry.oldSubject })}</p>{/if}
              </div>
              <button type="button" class="inline-flex min-h-11 shrink-0 items-center gap-2 rounded-xl border border-violet-300 bg-violet-50 px-3 py-2 text-sm font-bold text-violet-800 shadow-sm dark:border-violet-800 dark:bg-violet-950/50 dark:text-violet-200" aria-label={$t('entry.adjust_named', { name: displayName })} title={$t('entry.adjust_named', { name: displayName })} on:click={() => openSubject(entry)}>
                <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z" /></svg>
                <span>{$t('entry.adjust_subject')}</span>
              </button>
            </div>
            <dl class="mt-3 grid gap-1.5 text-sm text-slate-700 dark:text-zinc-300">
              <div class="flex gap-2"><dt class="font-semibold">{$t('entry.time')}</dt><dd>{formatTime(entry.start)}–{formatTime(entry.end)}</dd></div>
              {#if rooms.length}<div class="flex gap-2"><dt class="font-semibold">{$t('entry.rooms')}</dt><dd>{rooms.join(', ')}</dd></div>{/if}
              {#if local?.teacher}<div class="flex gap-2"><dt class="font-semibold">{$t('entry.local_teacher')}</dt><dd>{local.teacher}</dd></div>{/if}
              {#if entry.comment}<div class="flex gap-2"><dt class="font-semibold">{$t('entry.note')}</dt><dd>{entry.comment}</dd></div>{/if}
            </dl>
          </article>
        {/each}
      </div>
    {/if}
  </section>

  {#if plan}<p class="mt-5 text-center text-xs text-slate-500 dark:text-zinc-400">{$t('app.updated')} <time datetime={plan.lastSuccessfulFetchAt}>{new Intl.DateTimeFormat($language, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(plan.lastSuccessfulFetchAt))}</time></p>{/if}
</main>

<dialog bind:this={settingsDialog} class="m-auto w-[calc(100%-2rem)] max-w-2xl rounded-3xl bg-white p-0 text-slate-950 shadow-2xl dark:bg-zinc-900 dark:text-white" aria-labelledby="settings-title">
  <form class="max-h-[88vh] overflow-y-auto p-6" on:submit|preventDefault={savePreferences}>
    <div class="flex items-start justify-between gap-4"><div><p class="text-xs font-bold uppercase tracking-[0.2em] text-violet-600">{$t('settings.kicker')}</p><h2 id="settings-title" class="mt-1 text-2xl font-bold">{$t('settings.title')}</h2></div><button type="button" class="rounded-xl px-3 py-2" aria-label={$t('settings.close')} on:click={() => settingsDialog.close()}>×</button></div>
    <p class="mt-3 text-slate-600 dark:text-zinc-300">{$t('settings.intro')}</p>
    <div class="mt-4 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-950 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-100"><strong>{$t('settings.beta_title')}</strong> {$t('settings.beta_text')}</div>
    <label class="mt-5 flex items-center gap-3 rounded-2xl border border-slate-200 p-4 font-semibold dark:border-zinc-700"><input type="checkbox" bind:checked={preferences.enabled} /> {$t('settings.use_filter')}</label>
    <div class="mt-5 grid gap-4 sm:grid-cols-2">
      <label class="font-semibold">{$t('settings.grade')}<select class="form-select mt-2 w-full rounded-xl border border-slate-300 px-3 py-2 dark:border-zinc-700" bind:value={preferences.grade}><option value="">{$t('common.select')}</option>{#each [5,6,7,8,9,10,11,12] as grade (grade)}<option value={String(grade)}>{grade}</option>{/each}</select></label>
      {#if Number(preferences.grade) <= 10}<label class="font-semibold">{$t('settings.class')}<select class="form-select mt-2 w-full rounded-xl border border-slate-300 px-3 py-2 uppercase dark:border-zinc-700" bind:value={preferences.classLetter}><option value="">{$t('common.select')}</option>{#each ['a','b','c'] as letter (letter)}<option value={letter}>{letter.toUpperCase()}</option>{/each}</select></label>{/if}
    </div>
    {#if preferences.grade}
      <fieldset class="mt-5"><legend class="font-bold">{$t('settings.courses')}</legend><p class="mt-1 text-sm text-slate-500">{$t(Number(preferences.grade) >= 11 ? 'settings.course_help_upper' : 'settings.course_help_lower')}</p>
        {#if gradeCourses.length}<div class="mt-3 grid gap-2 sm:grid-cols-2">{#each gradeCourses as code (code)}<label class="flex items-center gap-2 rounded-xl border border-slate-200 p-3 dark:border-zinc-700"><input type="checkbox" checked={preferences.courses.includes(code)} on:change={(event) => toggleCourse(code, event.currentTarget.checked)} /> {code}</label>{/each}</div>{:else}<p class="mt-3 rounded-xl bg-slate-100 p-3 text-sm dark:bg-zinc-800">{$t('settings.course_empty')}</p>{/if}
      </fieldset>
    {/if}
    <label class="mt-5 block font-semibold">{$t('settings.custom_courses')} <span class="font-normal">{$t('common.optional')}</span><input class="mt-2 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-zinc-700" bind:value={customCourses} maxlength="500" placeholder={$t('settings.custom_placeholder')} /><small class="mt-1 block font-normal text-slate-500">{$t('settings.custom_help')}</small></label>
    <div class="mt-6 flex flex-wrap justify-end gap-3"><button type="button" class="rounded-xl border border-red-300 px-4 py-2 font-bold text-red-700 dark:border-red-900 dark:text-red-300" on:click={resetPreferences}>{$t('settings.reset')}</button><button type="button" class="rounded-xl border border-slate-300 px-4 py-2 font-bold dark:border-zinc-700" on:click={() => settingsDialog.close()}>{$t('common.cancel')}</button><button type="submit" class="rounded-xl bg-violet-600 px-4 py-2 font-bold text-white">{$t('common.save')}</button></div>
  </form>
</dialog>

<dialog bind:this={subjectDialog} class="m-auto w-[calc(100%-2rem)] max-w-lg rounded-3xl bg-white p-0 text-slate-950 shadow-2xl dark:bg-zinc-900 dark:text-white" aria-labelledby="subject-title">
  <form class="p-6" on:submit|preventDefault={saveSubject}>
    <div class="flex justify-between gap-4"><h2 id="subject-title" class="text-2xl font-bold">{$t('subject.title')}</h2><button type="button" class="rounded-xl px-3 py-2" aria-label={$t('common.dialog_close')} on:click={() => subjectDialog.close()}>×</button></div>
    <p class="mt-2 text-sm text-slate-500">{$t('subject.intro')}</p>
    <label class="mt-5 block font-semibold">{$t('subject.new_name')}<input class="mt-2 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-zinc-700" bind:value={editingOverride.name} maxlength="60" placeholder={$t('subject.name_placeholder')} /></label>
    <label class="mt-4 block font-semibold">{$t('subject.teacher')} <span class="font-normal">{$t('common.optional')}</span><input class="mt-2 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-zinc-700" bind:value={editingOverride.teacher} maxlength="60" placeholder={$t('subject.teacher_placeholder')} /></label>
    <fieldset class="mt-4">
      <legend class="font-semibold">{$t('subject.color')}</legend>
      <div class="mt-3 flex flex-wrap gap-3">
        <label class="color-choice" class:color-choice-selected={!editingOverride.color} title={$t('subject.color.standard')}>
          <input class="sr-only" type="radio" bind:group={editingOverride.color} value="" aria-label={$t('subject.color.standard')} />
          <span class="color-swatch color-swatch-standard" aria-hidden="true">×</span>
        </label>
        {#each Object.keys(colors) as color (color)}
          <label class="color-choice" class:color-choice-selected={editingOverride.color === color} title={$t(`subject.color.${color}`)}>
            <input class="sr-only" type="radio" bind:group={editingOverride.color} value={color} aria-label={$t(`subject.color.${color}`)} />
            <span class={`color-swatch ${colorSwatches[color]}`} aria-hidden="true"></span>
          </label>
        {/each}
      </div>
    </fieldset>
    <div class="mt-6 flex flex-wrap justify-end gap-3"><button type="button" class="rounded-xl border border-red-300 px-4 py-2 font-bold text-red-700 dark:border-red-900 dark:text-red-300" on:click={resetSubject}>{$t('subject.reset')}</button><button type="button" class="rounded-xl border border-slate-300 px-4 py-2 font-bold dark:border-zinc-700" on:click={() => subjectDialog.close()}>{$t('common.cancel')}</button><button type="submit" class="rounded-xl bg-violet-600 px-4 py-2 font-bold text-white">{$t('common.save')}</button></div>
  </form>
</dialog>

<dialog bind:this={feedbackDialog} class="m-auto w-[calc(100%-2rem)] max-w-lg rounded-3xl bg-white p-0 text-slate-950 shadow-2xl dark:bg-zinc-900 dark:text-white" aria-labelledby="feedback-title">
  <form class="p-6" on:submit|preventDefault={submitFeedback}>
    <div class="flex justify-between gap-4"><div><p class="text-xs font-bold uppercase tracking-[0.2em] text-violet-600">{$t('feedback.kicker')}</p><h2 id="feedback-title" class="mt-1 text-2xl font-bold">{$t('feedback.title')}</h2></div><button type="button" class="rounded-xl px-3 py-2" aria-label={$t('common.dialog_close')} on:click={() => feedbackDialog.close()}>×</button></div>
    <p class="mt-3 text-slate-600 dark:text-zinc-300">{$t('feedback.intro')}</p><p class="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/40 dark:text-amber-100"><strong>{$t('feedback.privacy_title')}</strong> {$t('feedback.privacy_text')}</p>
    <label class="mt-4 block font-semibold">{$t('feedback.message')}<textarea class="mt-2 min-h-32 w-full rounded-xl border border-slate-300 bg-transparent px-3 py-2 dark:border-zinc-700" bind:value={feedbackMessage} minlength="10" maxlength="1500" placeholder={$t('feedback.placeholder')}></textarea></label>
    <label class="mt-4 flex items-start gap-3 text-sm"><input class="mt-1" type="checkbox" bind:checked={feedbackConfirmed} /> <span>{$t('feedback.confirm')}</span></label>
    {#if feedbackStatus}<p class="mt-4 font-semibold" role="status">{$t(feedbackStatus)}</p>{/if}
    <div class="mt-6 flex justify-end gap-3"><button type="button" class="rounded-xl border border-slate-300 px-4 py-2 font-bold dark:border-zinc-700" on:click={() => feedbackDialog.close()}>{$t('common.cancel')}</button><button type="submit" class="rounded-xl bg-violet-600 px-4 py-2 font-bold text-white disabled:opacity-60" disabled={feedbackSending}>{$t(feedbackSending ? 'feedback.sending' : 'feedback.send')}</button></div>
  </form>
</dialog>

<dialog bind:this={transparencyDialog} class="m-auto w-[calc(100%-2rem)] max-w-2xl rounded-3xl bg-white p-0 text-slate-950 shadow-2xl dark:bg-zinc-900 dark:text-white" aria-labelledby="transparency-title" on:close={showDisclaimer}>
  <div class="max-h-[90vh] overflow-y-auto p-6 sm:p-8">
    <h2 id="transparency-title" class="text-3xl font-bold">{$t('transparency.title')}</h2>
    <p class="mt-5 leading-relaxed text-slate-700 dark:text-zinc-300">{$t('transparency.architecture')}</p>
    <p class="mt-4 leading-relaxed text-slate-700 dark:text-zinc-300">{$t('transparency.relay')}</p>
    <p class="mt-4 font-semibold text-slate-800 dark:text-zinc-200">{$t('transparency.costs')}</p>
    <button type="button" class="mt-6 w-full rounded-xl bg-violet-600 px-4 py-3 font-bold text-white" on:click={() => transparencyDialog.close()}>{$t('transparency.close')}</button>
  </div>
</dialog>

<dialog bind:this={disclaimerDialog} class="m-auto w-[calc(100%-2rem)] max-w-2xl rounded-3xl bg-white p-0 text-slate-950 shadow-2xl dark:bg-zinc-900 dark:text-white" aria-labelledby="disclaimer-title" on:cancel={(event) => event.preventDefault()}>
  <div class="max-h-[90vh] overflow-y-auto p-6 sm:p-8">
    <p class="text-xs font-bold uppercase tracking-[0.2em] text-violet-600">{$t('disclaimer.kicker')}</p><h2 id="disclaimer-title" class="mt-1 text-3xl font-bold">{$t('disclaimer.title')}</h2><p class="mt-4 text-slate-700 dark:text-zinc-300">{$t('disclaimer.private')}</p>
    {#each [['disclaimer.unofficial.title','disclaimer.unofficial.text'],['disclaimer.warranty.title','disclaimer.warranty.text'],['disclaimer.binding.title','disclaimer.binding.text'],['disclaimer.privacy.title','disclaimer.privacy.text']] as notice (notice[0])}<section class="mt-4 rounded-2xl bg-slate-100 p-4 dark:bg-zinc-800"><h3 class="font-bold">{$t(notice[0])}</h3><p class="mt-1 text-sm leading-relaxed">{$t(notice[1])}</p></section>{/each}
    <label class="mt-5 flex items-start gap-3 rounded-2xl border border-violet-300 p-4 font-semibold dark:border-violet-900"><input class="mt-1" type="checkbox" bind:checked={disclaimerConfirmed} /> <span>{$t('disclaimer.confirm')}</span></label>
    <button type="button" class="mt-5 w-full rounded-xl bg-violet-600 px-4 py-3 font-bold text-white disabled:opacity-50" disabled={!disclaimerConfirmed} on:click={acceptDisclaimer}>{$t('disclaimer.continue')}</button>
  </div>
</dialog>
