import SwiftUI
import AppKit

// Точка входа Pipboy для macOS. Окно = WKWebView с нашим веб-интерфейсом.
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
            .background(WindowMaximizer())   // окно на всю ширину экрана (не фуллскрин)
            .onAppear { server.start() }
        }
        .windowStyle(.hiddenTitleBar)
    }
}

// Растягивает окно на всю видимую область экрана (без режима «во весь экран»).
struct WindowMaximizer: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let v = NSView()
        DispatchQueue.main.async {
            if let w = v.window, let screen = w.screen ?? NSScreen.main {
                w.setFrame(screen.visibleFrame, display: true, animate: false)
            }
        }
        return v
    }
    func updateNSView(_ nsView: NSView, context: Context) {}
}
