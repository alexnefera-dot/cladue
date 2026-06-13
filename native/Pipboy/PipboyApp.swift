import SwiftUI

// Точка входа нативного приложения Pipboy для macOS.
// Окно = WKWebView с нашим веб-интерфейсом. Node-сервер поднимается рядом.
@main
struct PipboyApp: App {
    @StateObject private var server = ServerProcess()
    @State private var unlocked = false

    var body: some Scene {
        WindowGroup("Pipboy") {
            ZStack {
                if unlocked {
                    WebView(url: URL(string: "http://localhost:7777")!)
                        .ignoresSafeArea()
                } else {
                    AuthGate(unlocked: $unlocked)
                }
            }
            .frame(minWidth: 1100, minHeight: 760)
            .onAppear { server.start() }
        }
        .windowStyle(.hiddenTitleBar)
    }
}
