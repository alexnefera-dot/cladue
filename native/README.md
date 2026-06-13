# Pipboy — нативное приложение (Swift, macOS → iPhone)

Настоящий .app без Chrome и без npm. Окно = WKWebView (родной движок Apple)
с нашим веб-интерфейсом внутри; сверху — нативный Touch ID и уведомления.
Весь фронт переиспользуется как есть.

## Что нужно (один раз)
1. Xcode из App Store (бесплатно, большой — ставится долго).
2. Для iPhone позже: Apple Developer Program ($99/год). Для Mac не обязателен.

## Сборка Mac-версии (по шагам, делаем вместе)
1. Открой Xcode → Create New Project → **macOS** → **App** → Next.
2. Product Name: `Pipboy` · Interface: **SwiftUI** · Language: **Swift** → создай
   проект в любой папке (например ~/Downloads).
3. В созданном проекте удали стандартные `PipboyApp.swift` и `ContentView.swift`.
4. Перетащи в проект 5 файлов из этой папки (native/Pipboy/):
   PipboyApp.swift, WebView.swift, AuthGate.swift, ServerProcess.swift, Notifications.swift.
5. Слева выбери проект → target Pipboy → вкладка **Signing & Capabilities**:
   - сними галку **App Sandbox** (нужно, чтобы запускать node и ходить на localhost),
     или добавь исключения для сети.
   - в **Info** добавь ключ `App Transport Security Settings` →
     `Allow Arbitrary Loads` = YES (для http://localhost).
   - системные напоминания работают сразу (UserNotifications), отдельная capability
     для локальных пушей не нужна — при первом включении тумблера в «Рутины»
     macOS сам спросит разрешение.
6. Проверь путь к репозиторию в ServerProcess.swift (repoRoot):
   по умолчанию ~/Downloads/cladue — поправь, если папка в другом месте.
7. Нажми ▶ (Run). Должно открыться окно с Touch ID, затем приложение.

## Дальше
- Уведомления о рутинах — готово (Notifications.swift): тумблер «🔔 системные
  напоминания» в «Рутины» шлёт расписание в UNUserNotificationCenter, пуш
  приходит ежедневно в ⏰ время даже при закрытом окне.
- Авто-замок по бездействию — готово (IdleLocker в PipboyApp.swift): палец при
  запуске разблокирует всё, а через 10 минут без мыши/клавиатуры приложение
  само возвращает экран Touch ID. Поправить таймаут — константа timeout (сек).
- iPhone: тот же WKWebView, но данные — локальная SQLite на устройстве
  (Node на телефоне не крутится); синк с Mac по Wi-Fi. Отдельный таргет.

## Почему так
- Swift не использует npm — обходит то, что ломалось с Electron.
- WKWebView = тот же UI, но в родном окне Apple, с настоящим Touch ID.
