import SwiftUI
import AppKit

// Точка входа Pipboy для macOS. Окно = WKWebView с нашим веб-интерфейсом.
@main
struct PipboyApp: App {
    @StateObject private var server = ServerProcess()
    @StateObject private var idle = IdleLocker()
    @State private var unlocked = false

    var body: some Scene {
        WindowGroup("Pipboy") {
            ZStack {
                if unlocked {
                    WebView()
                        .ignoresSafeArea()
                } else {
                    AuthGate(unlocked: $unlocked)
                }
            }
            .background(WindowMaximizer())   // окно на всю ширину экрана (не фуллскрин)
            .onAppear { server.start(); idle.start() }
            // Простой 10 минут → закрываем разделы: возвращаем экран Touch ID.
            .onReceive(idle.$locked) { locked in if locked { unlocked = false } }
            // После разблокировки пальцем — снова считаем бездействие с нуля.
            .onChange(of: unlocked) { now in if now { idle.resumeAfterUnlock() } }
        }
        .windowStyle(.hiddenTitleBar)
    }
}

// Авто-замок по бездействию. Любая мышь/клавиша перезапускает 10-минутный отсчёт;
// когда время вышло — поднимаем флаг locked, и приложение показывает AuthGate
// (палец). При запуске разблокировал пальцем — внутри сессии больше не спрашивает,
// пока активно работаешь; забыл закрыть и отошёл на 10 минут — заблокируется само.
final class IdleLocker: ObservableObject {
    @Published var locked = false
    private let timeout: TimeInterval = 600   // 10 минут
    private var timer: Timer?
    private var monitor: Any?

    func start() {
        if monitor == nil {
            monitor = NSEvent.addLocalMonitorForEvents(
                matching: [.mouseMoved, .leftMouseDown, .rightMouseDown,
                           .leftMouseDragged, .keyDown, .scrollWheel]
            ) { [weak self] event in self?.poke(); return event }
        }
        arm()
    }

    // Активность пользователя — пока не заблокированы, сбрасываем таймер.
    private func poke() { if !locked { arm() } }

    // Палец принят — снимаем замок и заводим отсчёт заново.
    func resumeAfterUnlock() { locked = false; arm() }

    private func arm() {
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: timeout, repeats: false) { [weak self] _ in
            self?.locked = true
        }
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
