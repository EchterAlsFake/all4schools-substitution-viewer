import { derived, get, writable } from 'svelte/store';

type Catalog = Record<string, string>;
type Replacements = Record<string, string | number>;

export interface LanguageDefinition {
  code: string;
  name: string;
  status: string;
  flag: string;
}

const sourceCatalog = writable<Catalog>({});
const activeCatalog = writable<Catalog>({});
export const language = writable('de');
export const languages = writable<LanguageDefinition[]>([]);
export const i18nReady = writable(false);

function interpolate(value: string, replacements: Replacements): string {
  return value.replace(/\{([A-Za-z0-9_]+)\}/g, (match, key: string) =>
    Object.prototype.hasOwnProperty.call(replacements, key)
      ? String(replacements[key])
      : match,
  );
}

export const t = derived(
  [sourceCatalog, activeCatalog],
  ([$source, $active]) =>
    (key: string, replacements: Replacements = {}): string =>
      interpolate($active[key] || $source[key] || key, replacements),
);

async function loadCatalog(code: string): Promise<Catalog> {
  const response = await fetch(`/i18n/${encodeURIComponent(code)}.json`, {
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
  });
  if (!response.ok) throw new Error('catalog_unavailable');
  const raw = (await response.json()) as Record<string, unknown>;
  return Object.fromEntries(
    Object.entries(raw).filter((entry): entry is [string, string] => typeof entry[1] === 'string'),
  );
}

export async function initializeI18n(): Promise<void> {
  const [source, languageResponse] = await Promise.all([
    loadCatalog('de'),
    fetch('/i18n/languages.json', { credentials: 'omit', referrerPolicy: 'no-referrer' }),
  ]);
  sourceCatalog.set(source);
  const metadata = (await languageResponse.json()) as { languages?: LanguageDefinition[] };
  const available = Array.isArray(metadata.languages) ? metadata.languages : [];
  languages.set(available);
  let requested = 'de';
  try {
    requested = localStorage.getItem('vplan-language') || 'de';
  } catch {
    requested = 'de';
  }
  if (!available.some((item) => item.code === requested)) requested = 'de';
  await changeLanguage(requested);
  i18nReady.set(true);
}

export async function changeLanguage(code: string): Promise<void> {
  const available = get(languages);
  const safeCode = available.some((item) => item.code === code) ? code : 'de';
  const catalog: Catalog = safeCode === 'de'
    ? get(sourceCatalog)
    : await loadCatalog(safeCode).catch((): Catalog => ({}));
  activeCatalog.set(catalog);
  language.set(safeCode);
  document.documentElement.lang = safeCode;
  document.title = (catalog['app.title'] || get(sourceCatalog)['app.title'] || 'Vertretungsplan');
  const description = document.querySelector<HTMLMetaElement>('meta[name="description"]');
  if (description) {
    description.content = catalog['app.description'] || get(sourceCatalog)['app.description'] || '';
  }
  try {
    localStorage.setItem('vplan-language', safeCode);
  } catch {
    // The UI remains usable when browser storage is disabled.
  }
}
