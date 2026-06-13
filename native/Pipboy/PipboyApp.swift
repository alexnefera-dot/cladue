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

// Разворачивает окно на всю видимую область экрана. С повтором —
// окно может появиться позже самого view, поэтому ждём его.
struct WindowMaximizer: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let v = NSView()
        maximize(v, attempts: 0)
        return v
    }
    func updateNSView(_ nsView: NSView, context: Context) {}

    private func maximize(_ v: NSView, attempts: Int) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            if let w = v.window, let screen = w.screen ?? NSScreen.main {
                w.setFrame(screen.visibleFrame, display: true, animate: false)
            } else if attempts < 30 {
                maximize(v, attempts: attempts + 1)
            }
        }
    }
}
