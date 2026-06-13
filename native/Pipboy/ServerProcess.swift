import Foundation

// Поднимает Node-сервер (app/server.js) рядом. При каждом запуске:
// git pull → перезапуск сервера со свежим кодом → ты всегда на актуальной версии.
// Всё в фоновом потоке: UI не блокируется, SIGTERM не возникает.
final class ServerProcess: ObservableObject {
    private var proc: Process?

    func start() {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.run()
        }
    }

    private func run() {
        let repo = repoRoot()
        runGitPull(in: repo)                 // подтянуть свежий код
        killPort7777()                       // погасить старый сервер (даже со старым кодом)
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
        // подождать, пока сервер ответит (для WebView)
        for _ in 0..<60 { if ping() { break }; usleep(250_000) }
    }

    private func killPort7777() {
        guard let lsof = firstExecutable(["/usr/sbin/lsof", "/usr/bin/lsof"]) else { return }
        let find = Process(); find.executableURL = lsof; find.arguments = ["-ti", ":7777"]
        let pipe = Pipe(); find.standardOutput = pipe
        try? find.run(); find.waitUntilExit()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        guard let out = String(data: data, encoding: .utf8) else { return }
        for pidStr in out.split(whereSeparator: { $0 == "\n" || $0 == " " }) {
            if let pid = Int32(pidStr.trimmingCharacters(in: .whitespaces)) { kill(pid, SIGTERM) }
        }
        usleep(400_000)
    }

    private func runGitPull(in repo: URL) {
        guard let git = firstExecutable(["/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git"]) else { return }
        let p = Process(); p.executableURL = git
        p.arguments = ["-C", repo.path, "pull", "--quiet"]
        var env = ProcessInfo.processInfo.environment
        env["GIT_TERMINAL_PROMPT"] = "0"     // не виснуть на запросе пароля git
        p.environment = env
        do {
            try p.run()
            let deadline = Date().addingTimeInterval(8)
            while p.isRunning && Date() < deadline { usleep(100_000) }
            if p.isRunning { p.terminate() }
        } catch { /* git недоступен — стартуем на текущем коде */ }
    }

    private func ping() -> Bool {
        let sem = DispatchSemaphore(value: 0); var ok = false
        var req = URLRequest(url: URL(string: "http://localhost:7777/api/info")!); req.timeoutInterval = 1
        URLSession.shared.dataTask(with: req) { _, resp, _ in
            ok = (resp as? HTTPURLResponse)?.statusCode == 200; sem.signal()
        }.resume()
        _ = sem.wait(timeout: .now() + 1.2); return ok
    }

    private func findNode() -> URL? {
        firstExecutable(["/opt/homebrew/bin/node", "/usr/local/bin/node", "/usr/bin/node"])
    }
    private func firstExecutable(_ paths: [String]) -> URL? {
        for p in paths where FileManager.default.isExecutableFile(atPath: p) { return URL(fileURLWithPath: p) }
        return nil
    }
    private func repoRoot() -> URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Downloads/cladue")
    }
}
