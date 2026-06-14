import SwiftUI
import LocalAuthentication

// Нативный замок macOS: Touch ID (или системный пароль). Тем же проходом
// достаём ключ базы из Keychain под биометрией и кладём в KeyHolder —
// scheme-handler берёт уже готовый ключ, второго запроса пальца нет.
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
        if ctx.canEvaluatePolicy(.deviceOwnerAuthentication, error: &err) {
            ctx.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Доступ к Pipboy") { ok, _ in
                if ok {
                    // ключ базы под тем же пальцем (без второго запроса) → держателю
                    KeyHolder.shared.key = try? Keychain.databaseKey(context: ctx)
                    DispatchQueue.main.async { unlocked = true }
                    DispatchQueue.global().async {
                        if let key = KeyHolder.shared.key { Importer.importIfNeeded(encryptedKey: key) }
                    }
                } else {
                    DispatchQueue.main.async { error = "Не удалось разблокировать" }
                }
            }
        } else {
            error = "Аутентификация недоступна на этом Mac"
        }
    }
}
