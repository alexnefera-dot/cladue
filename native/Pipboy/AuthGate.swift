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
                NSLog(Database.sqlcipherActive
                    ? "Pipboy: SQLCipher активен (шифрование доступно)"
                    : "Pipboy: ВНИМАНИЕ — SQLCipher НЕ подключён к таргету, идёт системный SQLite без шифрования")
                let key = try Keychain.databaseKey()
                Importer.importIfNeeded(encryptedKey: key)        // Этап 0b: разовый импорт
                let db = try Database(key: key)
                let tables = try db.scalarInt("SELECT count(*) FROM sqlite_master WHERE type='table'")
                let nodes = (try? db.scalarInt("SELECT count(*) FROM nodes")) ?? 0
                NSLog("Pipboy 0b: зашифрованная база — таблиц:\(tables) задач:\(nodes)")
                // Этап 1: проверяем нативный /api/tree (тот же ответ, что давал Node).
                let (treeData, _) = try Api.handle(path: "/api/tree", query: nil, db: db)
                let obj = try JSONSerialization.jsonObject(with: treeData) as? [String: Any]
                let treeNodes = (obj?["nodes"] as? [[String: Any]])?.count ?? -1
                let links = (obj?["links"] as? [[String: Any]])?.count ?? -1
                NSLog("Pipboy 1: нативный /api/tree — узлов:\(treeNodes) связей:\(links)")
                // Этап 1: проверяем тяжёлый /api/fin (портфель + конвертация валют).
                let (finData, _) = try Api.handle(path: "/api/fin", query: nil, db: db)
                let fin = try JSONSerialization.jsonObject(with: finData) as? [String: Any]
                let blocks = (fin?["portfolio"] as? [[String: Any]])?.count ?? -1
                let total = ((fin?["summary"] as? [String: Any])?["portfolioTotal"] as? Double) ?? -1
                NSLog("Pipboy 1: нативный /api/fin — блоков:\(blocks) портфель €\(Int(total))")
                // Этап 1: дашборд (тянет календарь+финансы+людей — самый связанный эндпоинт).
                let (tdData, _) = try Api.handle(path: "/api/today", query: nil, db: db)
                let td = try JSONSerialization.jsonObject(with: tdData) as? [String: Any]
                let rout = (td?["routines"] as? [[String: Any]])?.count ?? -1
                let over = (td?["overdue"] as? [[String: Any]])?.count ?? -1
                NSLog("Pipboy 1: нативный /api/today — рутин:\(rout) просрочено:\(over)")
            } catch {
                NSLog("Pipboy 0b: ошибка шифр-базы: \(error)")
            }
        }
    }
}
