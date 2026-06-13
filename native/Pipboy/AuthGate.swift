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
                        Self.smokeTestEncryptedDB(context: ctx)   // Этап 0a (временно)
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
    static func smokeTestEncryptedDB(context: LAContext) {
        DispatchQueue.global().async {
            do {
                let key = try Keychain.databaseKey(context: context)
                let n = try Database(key: key).smokeTest()
                NSLog("Pipboy 0a: зашифрованная база открыта, _smoke=\(n)")
            } catch {
                NSLog("Pipboy 0a: ошибка шифр-базы: \(error)")
            }
        }
    }
}
