# Pipboy — упаковка и релиз

Прежде чем собирать — прогони пред-полётную проверку из корня репозитория:

```bash
bash scripts/package-preflight.sh
```

Она сверяет фронт в бандле iOS с `app/public`, гоняет тесты, проверяет синтаксис
и печатает ручной чек-лист для Xcode.

---

## Что уже настроено в проекте (проверено)

| Параметр | Значение |
|---|---|
| Таргеты | **Pipboy** (macOS, `com.pipboy.app`) · **Pipboy iOS** (`local.pipboy.Pipboy-iOS`) + тесты |
| Команда подписи | `DEVELOPMENT_TEAM = 6D7A8LBJG4`, Automatic signing |
| Deployment | macOS 13.0 · iOS 18.2 |
| Шифрование БД | **SQLCipher (skiptools/swift-sqlcipher) привязан к обоим таргетам** → `Database.sqlcipherActive == true`, база реально шифруется ✓ |
| iOS-разрешения | `NSLocalNetworkUsageDescription` и `NSFaceIDUsageDescription` заданы через `INFOPLIST_KEY_*`; `NSBonjourServices=_pipboy._tcp` в `Pipboy-iOS-Info.plist` ✓ |
| macOS-разрешения | сеть/Bonjour в `native/Pipboy/Info.plist`, ATS с `NSAllowsLocalNetworking` ✓ |

Две вещи, которые НЕ настроены и нужны только для распространения за пределы
твоих устройств (для запуска на своём Mac/iPhone — не обязательны):

1. **macOS Hardened Runtime = NO.** Для нотаризации `.app` нужно `YES`
   (Target → Signing & Capabilities → Hardened Runtime).
2. **macOS не бандлит фронт.** Сейчас Mac читает фронт из `~/Downloads/cladue/app/public`
   (живой клон — удобно для разработки). Код уже умеет фоллбэк на бандл: если в
   `.app` есть `public/index.html`, возьмёт его. Чтобы `.app` работал на другом Mac —
   добавь `app/public` в таргет **Pipboy** как **folder reference** (синяя папка) в
   Copy Bundle Resources. На твоём Mac с клоном поведение не изменится.

---

## iPhone (основной сценарий — своё устройство)

1. Подключи iPhone, выбери его как destination, схему **Pipboy iOS**.
2. Product → Run (`⌘R`) — Xcode подпишет твоим Team и поставит на телефон.
3. Первый запуск: разреши **Face ID** и **локальную сеть** (iOS спросит — строки
   уже заданы).
4. Хочешь без кабеля/на пару устройств — **TestFlight**: Product → Archive →
   Distribute App → App Store Connect → TestFlight (нужен платный Apple Developer).

## Mac

**Для себя (просто пользоваться):**
1. Схема **Pipboy**, Product → Archive.
2. Organizer → Distribute App → **Custom → Copy App** (или Direct Distribution).
3. Готовый `Pipboy.app` положи в `/Applications`. Если фронт берётся из клона —
   оставь `~/Downloads/cladue` на месте; если забандлил `public/` (см. выше) — `.app`
   самодостаточен.

**Раздать на другой Mac (нотаризация):**
1. Включи **Hardened Runtime = YES**, забандли `public/` (см. выше).
2. Archive → Distribute App → **Developer ID** → Upload (Xcode сам нотаризует и
   застейплит).
3. Заверни в `.dmg` (например `create-dmg`) и раздавай.

---

## Поднять версию перед релизом

В настройках обоих таргетов:
- `MARKETING_VERSION` (CFBundleShortVersionString) — напр. `1.0` → `1.1`
- `CURRENT_PROJECT_VERSION` (CFBundleVersion) — инкремент (TestFlight требует
  уникальный build number на каждую загрузку).

---

## Чек-лист релиза

- [ ] `bash scripts/package-preflight.sh` → `PRE-FLIGHT OK`
- [ ] Xcode: **SQLCipher** в обоих таргетах (Frameworks) — база шифруется
- [ ] Версии подняты (оба таргета)
- [ ] Фронт в бандле iOS актуален (скрипт синхронизирует автоматически; **пересобрать**
      iOS-таргет, чтобы попало в `.ipa`)
- [ ] iOS: Face ID и локальная сеть разрешаются при первом запуске
- [ ] Синхрон: первая связка сверяется кодом (SAS-гейт) — обнови **оба** устройства вместе
- [ ] Безопасность: см. `docs/SECURITY-REVIEW.md` (исправленное + отложенный бэклог)
