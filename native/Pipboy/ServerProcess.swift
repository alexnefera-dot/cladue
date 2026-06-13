import Foundation

// Поднимает Node-сервер (app/server.js) рядом с приложением, если он ещё не запущен.
final class ServerProcess: ObservableObject {
    private var proc: Process?

    func start() {
        // уже поднят на 7777? — ничего не делаем
        if ping() { return }
        guard let node = findNode() else {
            NSLog("Pipboy: node не найден — установи Node.js")
            return
        }
        // путь к репозиторию: рядом с .app лежит папка app/ (настраивается в Настройках сборки)
        let appDir = repoRoot().appendingPathComponent("app")
        let p = Process()
        p.executableURL = node
        p.arguments = [appDir.appendingPathComponent("server.js").path]
        p.currentDirectoryURL = appDir
        try? p.run()
        proc = p
    }

    private func ping() -> Bool {
        let sem = DispatchSemaphore(value: 0)
        var ok = false
        var req = URLRequest(url: URL(string: "http://localhost:7777/api/info")!)
        req.timeoutInterval = 1
        URLSession.shared.dataTask(with: req) { _, resp, _ in
            ok = (resp as? HTTPURLResponse)?.statusCode == 200
            sem.signal()
        }.resume()
        _ = sem.wait(timeout: .now() + 1.2)
        return ok
    }

    private func findNode() -> URL? {
        for path in ["/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"] {
            if FileManager.default.isExecutableFile(atPath: path) { return URL(fileURLWithPath: path) }
        }
        return nil
    }

    // Путь к репозиторию cladue. По умолчанию ~/Downloads/cladue — поправим под тебя.
    private func repoRoot() -> URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Downloads/cladue")
    }
}
