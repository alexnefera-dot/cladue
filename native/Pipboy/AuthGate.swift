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
                    if ok { unlocked = true }
                    else { error = "Не удалось разблокировать" }
                }
            }
        } else {
            error = "Аутентификация недоступна на этом Mac"
        }
    }
}
