import { mount } from 'svelte';

import App from './App.svelte';
import './app.css';

declare global {
  interface Window {
    deferredInstallPrompt?: BeforeInstallPromptEvent;
  }

  interface BeforeInstallPromptEvent extends Event {
    prompt(): Promise<void>;
    userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
  }
}

try {
  const storedTheme = localStorage.getItem('vplan-theme');
  document.documentElement.classList.toggle('dark', storedTheme !== 'light');
} catch {
  document.documentElement.classList.add('dark');
}

window.addEventListener('beforeinstallprompt', (event) => {
  event.preventDefault();
  window.deferredInstallPrompt = event as BeforeInstallPromptEvent;
});

if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', async () => {
    const registrations = await navigator.serviceWorker.getRegistrations();
    await Promise.all(
      registrations
        .filter((registration) => new URL(registration.scope).pathname === '/vplan')
        .map((registration) => registration.unregister()),
    );
    await navigator.serviceWorker.register('/sw.js', { scope: '/' });
  });
}

mount(App, { target: document.getElementById('app')! });
