// Pipboy для Mac: тонкая Electron-оболочка вокруг существующего сервера.
// Ядро (app/) не знает про Electron — логика остаётся общей с веб и iOS-версиями.
const { app, BrowserWindow, Notification } = require('electron');
const { fork } = require('child_process');
const path = require('path');

const PORT = 7777;
let serverProc = null;

function startServer() {
  serverProc = fork(path.join(__dirname, '..', 'app', 'server.js'), [], {
    env: { ...process.env, PORT: String(PORT) },
    stdio: 'inherit',
  });
}

async function waitServer(tries = 40) {
  for (let i = 0; i < tries; i++) {
    try { await fetch(`http://127.0.0.1:${PORT}/api/info`); return true; }
    catch { await new Promise(r => setTimeout(r, 250)); }
  }
  return false;
}

async function createWindow() {
  startServer();
  await waitServer();
  const win = new BrowserWindow({
    width: 1380, height: 900,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#f6f7f9',
  });
  win.loadURL(`http://127.0.0.1:${PORT}`);
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { /* живём в доке, сервер не гасим */ });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
app.on('before-quit', () => serverProc?.kill());

// Нативные уведомления Mac: единая лента ядра /api/notify/upcoming.
// Своя озвучка на категорию; каждый ключ показываем один раз в день.
const SOUND = { routine: 'Glass', money: 'Funk', event: 'Ping', people: 'Hero' };
const shown = new Set();
setInterval(async () => {
  try {
    const items = await fetch(`http://127.0.0.1:${PORT}/api/notify/upcoming`).then(x => x.json());
    for (const n of Array.isArray(items) ? items : []) {
      if (shown.has(n.key)) continue;
      shown.add(n.key);
      new Notification({ title: n.title, body: n.body, sound: SOUND[n.category] ?? 'Glass' }).show();
    }
    if (shown.size > 500) shown.clear();   // ключи дневные — память не растим
  } catch { /* сервер занят или замок без ключа — пропускаем тик */ }
}, 60_000);
