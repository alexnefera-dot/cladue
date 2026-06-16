/* Минимальный service worker: нужен для установки на хоумскрин.
   Ничего не кэширует — данные всегда живые с локального сервера. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
