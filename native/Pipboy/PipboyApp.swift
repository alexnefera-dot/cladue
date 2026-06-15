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
    @StateObject private var sync = SyncService()
    @State private var unlocked = false
    @State private var reloadToken = 0          // ++ после применения снимка → перезагрузка фронта
    @State private var showSync = false
    #if os(iOS)
    @Environment(\.scenePhase) private var scenePhase
    #endif

    var body: some Scene {
        WindowGroup("Pipboy") {
            ZStack {
                if unlocked {
                    WebView(sync: sync, reloadToken: reloadToken).ignoresSafeArea()
                        // Нативная кнопка синхрона на ОБОИХ платформах — не зависит от
                        // веб-кнопки/моста, поэтому «раздать»/«получить» работает надёжно.
                        .overlay(alignment: .bottomTrailing) {
                            Button { showSync = true } label: {
                                Image(systemName: "arrow.triangle.2.circlepath")
                                    .font(.system(size: 17, weight: .bold)).foregroundStyle(.white)
                                    .padding(13).background(Color.accentColor, in: Circle()).shadow(radius: 3)
                            }
                            .buttonStyle(.plain).padding(.trailing, 16).padding(.bottom, 30)
                        }
                        .sheet(isPresented: $showSync) { SyncPanel(sync: sync) }
                } else {
                    AuthGate(unlocked: $unlocked)
                }
            }
            #if os(macOS)
            .background(WindowMaximizer())   // окно на всю ширину экрана (не фуллскрин)
            #endif
            .onAppear { server.start(); idle.start() }
            .onReceive(idle.$locked) { locked in if locked { unlocked = false } }
            .onReceive(sync.$appliedCount) { c in if c > 0 { reloadToken += 1 } }   // синхрон применён → перезагрузить фронт+данные
            .onChange(of: unlocked) { now in
                if now { idle.resumeAfterUnlock(); sync.autoStart() }   // открыли → авто-синхрон (если пара есть)
                else { sync.autoStop() }
            }
            #if os(iOS)
            .onChange(of: scenePhase) { phase in
                if phase == .background { unlocked = false; sync.autoStop() }   // ушёл из приложения → замок
                else if phase == .active && unlocked { sync.autoStart() }       // вернулся → синхрон
            }
            #endif
        }
        #if os(macOS)
        .windowStyle(.hiddenTitleBar)
        #endif
    }
}

// Нативная панель синхрона (iPhone): триггер не зависит от веб-фронта в бандле,
// поэтому работает, даже если bundled app.js ещё старый. На приёмнике «Получить»
// заменяет данные данными источника И обновляет сам фронт (приедет по Wi-Fi).
struct SyncPanel: View {
    @ObservedObject var sync: SyncService
    @Environment(\.dismiss) private var dismiss
    @State private var auto = SyncTrust.autoEnabled

    var body: some View {
        VStack(spacing: 14) {
            Text("Синхронизация Mac ↔ iPhone").font(.headline)
            Text(SyncTrust.paired ? "пара установлена · синхрон идёт автоматически при открытии"
                                  : "первая связка: на Mac «Раздать», тут «Получить», сверь код")
                .font(.caption).foregroundStyle(SyncTrust.paired ? Color.green : Color.gray).multilineTextAlignment(.center)
            Text(sync.status.isEmpty ? "оба устройства в одной Wi-Fi" : sync.status)
                .font(.callout).foregroundStyle(.secondary).multilineTextAlignment(.center)
            if !sync.sas.isEmpty {
                Text("код сверки: \(sync.sas)").font(.title2.weight(.bold).monospacedDigit())
                Text("должен совпасть на обоих устройствах").font(.caption).foregroundStyle(.secondary)
            }
            Toggle("Авто-синхрон", isOn: $auto)
                .onChange(of: auto) { v in SyncTrust.autoEnabled = v; if v { sync.autoStart() } else { sync.autoStop() } }
            VStack(spacing: 10) {
                Button { sync.receive() } label: {
                    Text(SyncTrust.paired ? "Синхронизировать сейчас" : "Получить данные с Mac").frame(maxWidth: .infinity)
                }.buttonStyle(.borderedProminent)
                Button { sync.host() } label: {
                    Text("Раздать данные").frame(maxWidth: .infinity)
                }.buttonStyle(.bordered)
                Button { sync.stop() } label: {
                    Text("Стоп").frame(maxWidth: .infinity)
                }.buttonStyle(.bordered)
            }
            Text("правки сходятся двусторонне · ничего не уходит в облако")
                .font(.caption2).foregroundStyle(.secondary).multilineTextAlignment(.center)
            Button("Закрыть") { dismiss() }.padding(.top, 4)
        }
        .padding(24).frame(maxWidth: 460)
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
