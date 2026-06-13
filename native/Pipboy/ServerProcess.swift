import Foundation

// Поднимает Node-сервер (app/server.js) рядом с приложением и
// на каждом запуске сам подтягивает свежий код (git pull) — обновляться
// = просто перезапустить Pipboy, без Запустить.command.
final class ServerProcess: ObservableObject {
    private var proc: Process?

    func start() {
        let repo = repoRoot()
        // авто-обновление веб-кода
        runGitPull(in: repo)
        // уже поднят на 7777? — ничего не делаем
        if ping() { return }
        guard let node = findNode() else {
            NSLog("Pipboy: node не найден — установи Node.js")
            return
        }
        let appDir = repo.appendingPathComponent("app")
        let p = Process()
        p.executableURL = node
        p.arguments = [appDir.appendingPathComponent("server.js").path]
        p.currentDirectoryURL = appDir
        try? p.run()
        proc = p
    }

    private func runGitPull(in repo: URL) {
        guard let git = firstExecutable(["/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git"]) else { return }
        let p = Process()
        p.executableURL = git
        p.arguments = ["-C", repo.path, "pull", "--quiet"]
        try? p.run()
        p.waitUntilExit()   // ждём обновления перед стартом сервера
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
        firstExecutable(["/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"])
    }

    private func firstExecutable(_ paths: [String]) -> URL? {
        for p in paths where FileManager.default.isExecutableFile(atPath: p) {
            return URL(fileURLWithPath: p)
        }
        return nil
    }

    // Путь к репозиторию cladue. По умолчанию ~/Downloads/cladue.
    private func repoRoot() -> URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Downloads/cladue")
    }
}
