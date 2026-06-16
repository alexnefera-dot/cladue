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
                // completion уже на фоновом потоке: готовим базу (импорт/сид) ДО показа UI,
                // чтобы первый /api/tree не попал на пустую/полузасеянную базу (гонка старта).
                if ok {
                    // ключ берём ТОЛЬКО при успехе; при сбое НЕ открываем (иначе пустой экран
                    // без ключа), а просим повторить — база при этом не трогается.
                    if let key = try? Keychain.databaseKey(context: ctx) {
                        KeyHolder.shared.key = key
                        Importer.importIfNeeded(encryptedKey: key)
                        DispatchQueue.main.async { unlocked = true }
                    } else {
                        DispatchQueue.main.async { error = "Не удалось получить ключ базы — попробуй ещё раз" }
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
