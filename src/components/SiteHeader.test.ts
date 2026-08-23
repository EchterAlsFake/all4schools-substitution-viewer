import { cleanup, fireEvent, render, screen, within } from '@testing-library/svelte';
import { afterEach, expect, it, vi } from 'vitest';

import { dayNavigation } from '../lib/day-navigation';
import SiteHeader from './SiteHeader.svelte';


afterEach(() => {
  cleanup();
  dayNavigation.set({ items: [], activeDate: '', selectDay: () => undefined });
  document.documentElement.classList.remove('dark');
});

it('renders the available days inside the main header and delegates selection', async () => {
  const selectDay = vi.fn();
  dayNavigation.set({
    items: [
      { date: '2026-08-24', entryCount: 1 },
      { date: '2026-08-25', entryCount: 4 },
    ],
    activeDate: '2026-08-24',
    selectDay,
  });

  render(SiteHeader);

  const navigation = screen.getByRole('navigation', { name: 'navigation.choose_day' });
  expect(navigation.closest('header')).not.toBeNull();
  const dayButtons = within(navigation).getAllByRole('button');
  expect(dayButtons[0]).toHaveAttribute('aria-pressed', 'true');
  expect(dayButtons[1]).toHaveAttribute('aria-pressed', 'false');

  await fireEvent.click(dayButtons[1]);

  expect(selectDay).toHaveBeenCalledWith('2026-08-25');
});

it('links to the public source code without exposing the opener context', () => {
  render(SiteHeader);

  const githubLink = screen.getByRole('link', { name: 'utility.github_label' });
  expect(githubLink).toHaveAttribute(
    'href',
    'https://github.com/EchterAlsFake/all4schools-substitution-viewer',
  );
  expect(githubLink).toHaveAttribute('target', '_blank');
  expect(githubLink).toHaveAttribute('rel', 'noopener noreferrer');
});
