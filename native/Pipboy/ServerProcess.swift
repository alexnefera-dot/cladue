import Foundation

// Поднимает Node-сервер (app/server.js) рядом и подтягивает свежий код.
// ВСЁ делает в фоновом потоке — главный поток (UI) не блокируется,
// поэтому никаких зависаний/SIGTERM.
final class ServerProcess: ObservableObject {
    private var proc: Process?

    func start() {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.run()
        }
    }

    private func run() {
        let repo = repoRoot()
        runGitPull(in: repo)            // авто-обновление веб-кода (в фоне)
        if ping() { return }           // уже поднят на 7777 — ничего не делаем
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
        // не зависнуть на запросе пароля git: отключаем интерактивность
        var env = ProcessInfo.processInfo.environment
        env["GIT_TERMINAL_PROMPT"] = "0"
        p.environment = env
        do {
            try p.run()
            // ждём максимум 8 секунд — если дольше, бросаем и идём дальше
            let deadline = Date().addingTimeInterval(8)
            while p.isRunning && Date() < deadline { usleep(100_000) }
            if p.isRunning { p.terminate() }
        } catch { /* git недоступен — просто стартуем сервер на текущем коде */ }
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

    private func repoRoot() -> URL {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Downloads/cladue")
    }
}
