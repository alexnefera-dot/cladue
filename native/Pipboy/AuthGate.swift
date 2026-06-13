import SwiftUI
import LocalAuthentication

// Нативный замок macOS: Touch ID, при отсутствии — системный пароль.
struct AuthGate: View {
    @Binding var unlocked: Bool
    @State private var error = ""

    var body: some View {
        VStack(spacing: 16) {
            Text("🔒 Pipboy").font(.system(size: 34, weight: .bold))
            Text("Разблокируй, чтобы открыть").foregroundStyle(.secondary)
            Button("Войти по Touch ID") { authenticate() }
                .buttonStyle(.borderedProminent)
            if !error.isEmpty { Text(error).foregroundStyle(.red).font(.caption) }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .onAppear { authenticate() }
    }

    func authenticate() {
        let ctx = LAContext()
        ctx.localizedFallbackTitle = "Ввести пароль"
        var err: NSError?
        // .deviceOwnerAuthentication = Touch ID, а если недоступен — системный пароль Mac
        if ctx.canEvaluatePolicy(.deviceOwnerAuthentication, error: &err) {
            ctx.evaluatePolicy(.deviceOwnerAuthentication,
                               localizedReason: "Доступ к Pipboy") { ok, e in
                DispatchQueue.main.async {
                    if ok {
                        unlocked = true
                        Self.smokeTestEncryptedDB()   // Этап 0b (временно)
                    } else { error = "Не удалось разблокировать" }
                }
            }
        } else {
            error = "Аутентификация недоступна на этом Mac"
        }
    }

    // Этап 0a (временная проверка): открыть зашифрованную базу тем же пальцем.
    // В фоне и с перехватом — если что-то не так, приложение продолжает работать.
    // Результат смотри в консоли Xcode: «Pipboy 0a: …». Удалим, когда слой созреет.
    static func smokeTestEncryptedDB() {
        DispatchQueue.global().async {
            do {
                let key = try Keychain.databaseKey()
                Importer.importIfNeeded(encryptedKey: key)        // Этап 0b: разовый импорт
                let db = try Database(key: key)
                let tables = try db.scalarInt("SELECT count(*) FROM sqlite_master WHERE type='table'")
                let nodes = (try? db.scalarInt("SELECT count(*) FROM nodes")) ?? 0
                NSLog("Pipboy 0b: зашифрованная база — таблиц:\(tables) задач:\(nodes)")
            } catch {
                NSLog("Pipboy 0b: ошибка шифр-базы: \(error)")
            }
        }
    }
}
