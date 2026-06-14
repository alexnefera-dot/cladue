import Foundation

// Этап 3: Node убран. Данные — в зашифрованной базе через нативный слой (NativeAPI),
// интерфейс грузится из pipboy://. Здесь остаётся только авто-обновление веб-фронта:
// при запуске делаем git pull в репозитории, чтобы app/public был свежим.
// (Swift-изменения подтянутся тем же pull, но требуют пересборки в Xcode.)
final class ServerProcess: ObservableObject {
    func start() {
        DispatchQueue.global(qos: .utility).async { Self.gitPull(in: Self.repoRoot()) }
    }

    private static func gitPull(in repo: URL) {
        guard let git = firstExecutable(["/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git"]) else { return }
        let p = Process(); p.executableURL = git
        p.arguments = ["-C", repo.path, "pull", "--quiet", "--rebase", "--autostash"]
        var env = ProcessInfo.processInfo.environment
        env["GIT_TERMINAL_PROMPT"] = "0"     // не виснуть на запросе пароля git
        p.environment = env
        do {
            try p.run()
            let deadline = Date().addingTimeInterval(8)
            while p.isRunning && Date() < deadline { usleep(100_000) }
            if p.isRunning { p.terminate() }
        } catch { /* git недоступен — работаем на текущем коде */ }
    }

    private static func firstExecutable(_ paths: [String]) -> URL? {
        for p in paths where FileManager.default.isExecutableFile(atPath: p) { return URL(fileURLWithPath: p) }
        return nil
    }
    private static func repoRoot() -> URL {
        FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Downloads/cladue")
    }
}
