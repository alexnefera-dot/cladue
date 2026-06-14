import SwiftUI
#if os(macOS)
import AppKit
#endif

// Точка входа Pipboy (Mac + iPhone). Окно = WKWebView с веб-интерфейсом,
// данные — из зашифрованной базы (нативный слой).
@main
struct PipboyApp: App {
    @StateObject private var server = ServerProcess()
    @StateObject private var idle = IdleLocker()
    @State private var unlocked = false
    #if os(iOS)
    @Environment(\.scenePhase) private var scenePhase
    #endif

    var body: some Scene {
        WindowGroup("Pipboy") {
            ZStack {
                if unlocked {
                    WebView().ignoresSafeArea()
                } else {
                    AuthGate(unlocked: $unlocked)
                }
            }
            #if os(macOS)
            .background(WindowMaximizer())   // окно на всю ширину экрана (не фуллскрин)
            #endif
            .onAppear { server.start(); idle.start() }
            .onReceive(idle.$locked) { locked in if locked { unlocked = false } }
            .onChange(of: unlocked) { now in if now { idle.resumeAfterUnlock() } }
            #if os(iOS)
            .onChange(of: scenePhase) { phase in
                if phase == .background { unlocked = false }   // ушёл из приложения → замок
            }
            #endif
        }
        #if os(macOS)
        .windowStyle(.hiddenTitleBar)
        #endif
    }
}

// Авто-замок по бездействию. На Mac — слежение за мышью/клавиатурой (NSEvent) с
// 10-минутным таймером; на iOS бездействие ловит scenePhase (см. выше), здесь no-op.
final class IdleLocker: ObservableObject {
    @Published var locked = false

    #if os(macOS)
    private let timeout: TimeInterval = 600
    private var timer: Timer?
    private var monitor: Any?

    func start() {
        if monitor == nil {
            monitor = NSEvent.addLocalMonitorForEvents(
                matching: [.mouseMoved, .leftMouseDown, .rightMouseDown, .leftMouseDragged, .keyDown, .scrollWheel]
            ) { [weak self] event in self?.poke(); return event }
        }
        arm()
    }
    private func poke() { if !locked { arm() } }
    func resumeAfterUnlock() { locked = false; arm() }
    private func arm() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: timeout, repeats: false) { [weak self] _ in self?.locked = true }
    }
    #else
    func start() {}
    func resumeAfterUnlock() { locked = false }
    #endif
}

#if os(macOS)
// Разворачивает окно на всю видимую область экрана (с повтором — окно может появиться позже view).
struct WindowMaximizer: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView {
        let v = NSView(); maximize(v, attempts: 0); return v
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
#endif
