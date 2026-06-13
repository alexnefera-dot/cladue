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

// Нативные уведомления Mac: опрашиваем ядро о ближайших напоминаниях (рутины с временем)
setInterval(async () => {
  try {
    const r = await fetch(`http://127.0.0.1:${PORT}/api/routines`).then(x => x.json());
    const now = new Date();
    const hhmm = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    for (const rt of Array.isArray(r) ? r : [])
      if (rt.time === hhmm && !rt.done)
        new Notification({ title: '⏰ ' + rt.name, body: `Рутина на ${rt.time}` }).show();
  } catch { /* сервер занят/замок — пропускаем тик */ }
}, 60_000);
