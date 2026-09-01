import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/svelte';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

import type { PlanResponse } from '../lib/types';
import { TRANSPARENCY_NOTICE_STORAGE_KEY } from '../lib/storage';
import PlanApp from './PlanApp.svelte';


const plan: PlanResponse = {
  version: 'test-version',
  lastSuccessfulFetchAt: '2026-08-24T06:00:00+02:00',
  lastAttemptAt: '2026-08-24T06:00:00+02:00',
  sourceFrom: '2026-08-24T00:00:00+02:00',
  sourceTo: '2026-08-30T23:59:59+02:00',
  schoolYear: '2026/27',
  learnedCourseCodes: [],
  stale: false,
  days: [{
    date: '2026-08-24',
    entries: [{
      id: 'sport-entry',
      kind: 'change',
      start: '2026-08-24T08:35:00+02:00',
      end: '2026-08-24T09:20:00+02:00',
      oldSubject: 'Spo',
      newSubject: '',
      oldRooms: ['TH1'],
      newRooms: [],
      classes: ['5b'],
      comment: '',
    }],
  }],
};

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('vplan-disclaimer-accepted-v1', JSON.stringify(true));
  localStorage.setItem(TRANSPARENCY_NOTICE_STORAGE_KEY, JSON.stringify(true));
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(() => Promise.resolve(
      new Response(JSON.stringify(plan), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )),
  );
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) {
    this.setAttribute('open', '');
  });
  HTMLDialogElement.prototype.close = vi.fn(function (this: HTMLDialogElement) {
    this.removeAttribute('open');
    this.dispatchEvent(new Event('close'));
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it('applies and stores a custom subject name', async () => {
  const firstRender = render(PlanApp);

  expect(await screen.findByRole('heading', { name: 'Spo' })).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: 'entry.adjust_named' }));

  const dialog = screen.getByRole('dialog', { name: 'subject.title' });
  await fireEvent.input(within(dialog).getByLabelText('subject.new_name'), {
    target: { value: 'xD' },
  });
  await fireEvent.click(within(dialog).getByRole('button', { name: 'common.save' }));

  expect(JSON.parse(localStorage.getItem('vplan-subject-overrides') || '{}')).toMatchObject({
    '5b::spo': { name: 'xD' },
  });
  await waitFor(() => expect(screen.getByRole('heading', { name: 'xD' })).toBeInTheDocument());

  firstRender.unmount();
  render(PlanApp);
  expect(await screen.findByRole('heading', { name: 'xD' })).toBeInTheDocument();
});

it('uses explicit light and dark surfaces for personal-plan selects', async () => {
  render(PlanApp);

  expect(await screen.findByRole('heading', { name: 'Spo' })).toBeInTheDocument();
  await fireEvent.click(screen.getByRole('button', { name: /quick\.personal\.title/ }));

  const dialog = screen.getByRole('dialog', { name: 'settings.title' });
  const selects = within(dialog).getAllByRole('combobox');
  expect(selects).toHaveLength(2);
  expect(selects.every((select) => select.classList.contains('form-select'))).toBe(true);
});

it('shows and remembers the transparency notice only once', async () => {
  localStorage.removeItem(TRANSPARENCY_NOTICE_STORAGE_KEY);
  const firstRender = render(PlanApp);

  const dialog = await screen.findByRole('dialog', { name: 'transparency.title' });
  expect(JSON.parse(localStorage.getItem(TRANSPARENCY_NOTICE_STORAGE_KEY) || 'false')).toBe(true);
  await fireEvent.click(within(dialog).getByRole('button', { name: 'transparency.close' }));
  expect(screen.queryByRole('dialog', { name: 'transparency.title' })).not.toBeInTheDocument();

  firstRender.unmount();
  render(PlanApp);
  expect(await screen.findByRole('heading', { name: 'Spo' })).toBeInTheDocument();
  expect(screen.queryByRole('dialog', { name: 'transparency.title' })).not.toBeInTheDocument();
});

it('opens the mandatory disclaimer after the transparency notice closes', async () => {
  localStorage.removeItem(TRANSPARENCY_NOTICE_STORAGE_KEY);
  localStorage.removeItem('vplan-disclaimer-accepted-v1');
  render(PlanApp);

  const transparency = await screen.findByRole('dialog', { name: 'transparency.title' });
  expect(screen.queryByRole('dialog', { name: 'disclaimer.title' })).not.toBeInTheDocument();
  await fireEvent.click(within(transparency).getByRole('button', { name: 'transparency.close' }));

  expect(await screen.findByRole('dialog', { name: 'disclaimer.title' })).toBeInTheDocument();
});
