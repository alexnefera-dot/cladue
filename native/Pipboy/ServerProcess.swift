import Foundation

// Авто-обновление веб-фронта на Маке: при запуске git pull в репозитории, чтобы
// app/public был свежим. На iOS фронт вшит в бандл — здесь ничего не делаем.
final class ServerProcess: ObservableObject {
    func start() {
        #if os(macOS)
        DispatchQueue.global(qos: .utility).async { Self.gitPull(in: Self.repoRoot()) }
        #endif
    }

    #if os(macOS)
    private static func gitPull(in repo: URL) {
        guard let git = firstExecutable(["/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git"]) else { return }
        let p = Process(); p.executableURL = git
        p.arguments = ["-C", repo.path, "pull", "--quiet", "--rebase", "--autostash"]
        var env = ProcessInfo.processInfo.environment
        env["GIT_TERMINAL_PROMPT"] = "0"
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
    #endif
}
