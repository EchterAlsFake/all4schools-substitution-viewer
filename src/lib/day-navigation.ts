import { writable } from 'svelte/store';


export interface DayNavigationItem {
  date: string;
  entryCount: number;
}

export type SelectDay = (date: string) => void;

export interface DayNavigationState {
  items: DayNavigationItem[];
  activeDate: string;
  selectDay: SelectDay;
}

const noSelection: SelectDay = () => undefined;

function emptyState(): DayNavigationState {
  return { items: [], activeDate: '', selectDay: noSelection };
}

export const dayNavigation = writable<DayNavigationState>(emptyState());

export function clearDayNavigation(owner: SelectDay): void {
  dayNavigation.update((state) => state.selectDay === owner ? emptyState() : state);
}
