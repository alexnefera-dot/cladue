import SwiftUI
import WebKit
#if os(macOS)
import AppKit
#else
import UIKit
#endif

// Окно с веб-интерфейсом из зашифрованной базы (pipboy://). Кросс-платформенно:
// на Mac — NSViewRepresentable, на iOS — UIViewRepresentable. Coordinator общий:
// мост напоминаний + scheme-handler + JS-диалоги (alert/confirm/prompt) и внешние ссылки.
struct WebView {
    let sync: SyncService                       // общий с нативной панелью синхрона
    var reloadToken: Int = 0                    // ++ → перезагрузить страницу (после синхрона)
    func makeCoordinator() -> Coordinator { Coordinator(sync: sync) }

    fileprivate func makeWebView(_ coordinator: Coordinator) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.userContentController.add(coordinator.notifier, name: "pipboyReminders")
        // Нативный гейт — Touch ID/Face ID при запуске, поэтому веб-замок разделов лишний.
        // Помечаем сессию разблокированной ДО app.js (document-start), чтобы замок не
        // всплывал ни при какой версии фронта и не зависел от ответа /api/lock.
        let unlock = WKUserScript(
            source: "try{sessionStorage.setItem('pbUnlocked','1')}catch(e){}",
            injectionTime: .atDocumentStart, forMainFrameOnly: true)
        cfg.userContentController.addUserScript(unlock)
        cfg.userContentController.add(coordinator, name: "pipboySync")   // веб → нативный синхрон
        cfg.setURLSchemeHandler(coordinator.scheme, forURLScheme: PipboySchemeHandler.scheme)
        let v = WKWebView(frame: .zero, configuration: cfg)
        v.uiDelegate = coordinator
        coordinator.webView = v
        coordinator.bindSyncStatus()   // статус синхрона (в т.ч. авто-фонового) → в карточку Настроек
        v.load(URLRequest(url: URL(string: "pipboy://app/index.html")!))
        return v
    }

    final class Coordinator: NSObject, WKUIDelegate, WKScriptMessageHandler {
        let notifier = NotificationManager()
        let scheme = PipboySchemeHandler()
        let sync: SyncService
        weak var webView: WKWebView?
        var lastReload = 0                       // последний применённый reloadToken

        init(sync: SyncService) { self.sync = sync; super.init() }

        // Зеркалим статус синхрона в веб (window.pbSync) — один раз, чтобы и авто-фоновый
        // обмен показывался в Настройках, а не только инициированный из веба.
        func bindSyncStatus() {
            sync.onStatus = { [weak self] s in
                let esc = s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "'", with: "\\'")
                self?.webView?.evaluateJavaScript("window.pbSync&&window.pbSync('\(esc)')", completionHandler: nil)
                if s.contains("✓") { self?.pushState() }   // обмен прошёл → сразу обновить «пара установлена»/авто
            }
            // первая связка: показать код сверки + кнопки «совпадает/нет» в карточке Настроек
            sync.onSas = { [weak self] code in
                let esc = code.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "'", with: "\\'")
                self?.webView?.evaluateJavaScript("window.pbSyncSas&&window.pbSyncSas('\(esc)')", completionHandler: nil)
            }
            sync.onSasClear = { [weak self] in
                self?.webView?.evaluateJavaScript("window.pbSyncSasClear&&window.pbSyncSasClear()", completionHandler: nil)
            }
        }

        // Веб (Настройки) шлёт действия синхрона. Управление целиком в Настройках,
        // авто работает в фоне.
        func userContentController(_ uc: WKUserContentController, didReceive message: WKScriptMessage) {
            guard message.name == "pipboySync" else { return }
            let body = message.body as? [String: Any]
            let action = body?["action"] as? String ?? (message.body as? String) ?? ""
            switch action {
            case "sync", "host", "receive":           // «синхронизировать сейчас» / первая связка (роль по платформе)
                #if os(macOS)
                if action == "receive" { sync.receive() } else { sync.host() }
                #else
                if action == "host" { sync.host() } else { sync.receive() }
                #endif
            case "confirmSas":                        // пользователь сверил код первой связки
                sync.confirmSas(body?["ok"] as? Bool ?? false)
            case "stop": sync.stop(); sync.onStatus?("остановлено")
            case "auto":
                let on = body?["on"] as? Bool ?? true
                SyncTrust.autoEnabled = on
                if on { sync.autoStart() } else { sync.autoStop() }
                pushState()
            case "state": pushState()
            default: break
            }
        }

        // Текущее состояние пары/авто → в веб (window.pbSyncState).
        private func pushState() {
            let js = "window.pbSyncState&&window.pbSyncState({paired:\(SyncTrust.paired),auto:\(SyncTrust.autoEnabled)})"
            webView?.evaluateJavaScript(js, completionHandler: nil)
        }

        // ----- target=_blank ссылки → внешний браузер -----
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let url = navigationAction.request.url {
                #if os(macOS)
                NSWorkspace.shared.open(url)
                #else
                UIApplication.shared.open(url)
                #endif
            }
            return nil
        }

        // ----- JS alert/confirm/prompt -----
        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            #if os(macOS)
            let a = NSAlert(); a.messageText = "Pipboy"; a.informativeText = message
            a.addButton(withTitle: "OK"); a.runModal(); completionHandler()
            #else
            present(title: message, fields: 0) { _ in completionHandler() }
            #endif
        }
        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            #if os(macOS)
            let a = NSAlert(); a.messageText = "Pipboy"; a.informativeText = message
            a.addButton(withTitle: "OK"); a.addButton(withTitle: "Отмена")
            completionHandler(a.runModal() == .alertFirstButtonReturn)
            #else
            present(title: message, fields: 0, cancel: true) { ok in completionHandler(ok != nil) }
            #endif
        }
        func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String,
                     defaultText: String?, initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping (String?) -> Void) {
            #if os(macOS)
            let a = NSAlert(); a.messageText = "Pipboy"; a.informativeText = prompt
            a.addButton(withTitle: "OK"); a.addButton(withTitle: "Отмена")
            let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 320, height: 24))
            field.stringValue = defaultText ?? ""
            a.accessoryView = field
            a.window.initialFirstResponder = field
            completionHandler(a.runModal() == .alertFirstButtonReturn ? field.stringValue : nil)
            #else
            present(title: prompt, fields: 1, cancel: true, defaultText: defaultText) { completionHandler($0) }
            #endif
        }

        #if os(iOS)
        // Алерт/ввод на iOS через UIAlertController с верхнего контроллера.
        private func present(title: String, fields: Int, cancel: Bool = false, defaultText: String? = nil,
                             done: @escaping (String?) -> Void) {
            DispatchQueue.main.async {
                guard let vc = Self.topViewController() else { done(nil); return }
                let alert = UIAlertController(title: "Pipboy", message: title, preferredStyle: .alert)
                if fields == 1 { alert.addTextField { $0.text = defaultText } }
                alert.addAction(UIAlertAction(title: "OK", style: .default) { _ in
                    done(fields == 1 ? (alert.textFields?.first?.text ?? "") : "")
                })
                if cancel { alert.addAction(UIAlertAction(title: "Отмена", style: .cancel) { _ in done(nil) }) }
                vc.present(alert, animated: true)
            }
        }
        private static func topViewController() -> UIViewController? {
            let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
            let windows = scenes.flatMap { $0.windows }
            // isKeyWindow в SwiftUI-WKWebView бывает nil → откат к первому окну с rootVC,
            // иначе алерт (confirm удаления и т.п.) молча не показывается
            var top = (windows.first { $0.isKeyWindow } ?? windows.first { $0.rootViewController != nil } ?? windows.first)?.rootViewController
            while let p = top?.presentedViewController { top = p }
            return top
        }
        #endif
    }
}

#if os(macOS)
extension WebView: NSViewRepresentable {
    func makeNSView(context: Context) -> WKWebView { makeWebView(context.coordinator) }
    func updateNSView(_ nsView: WKWebView, context: Context) { reloadIfNeeded(nsView, context.coordinator) }
}
#else
extension WebView: UIViewRepresentable {
    func makeUIView(context: Context) -> WKWebView { makeWebView(context.coordinator) }
    func updateUIView(_ uiView: WKWebView, context: Context) { reloadIfNeeded(uiView, context.coordinator) }
}
#endif

extension WebView {
    // Синхрон применился — обновляем ТЕКУЩИЙ экран мягко (без перезагрузки страницы),
    // чтобы приложение не «подпрыгивало» и не сбрасывало навигацию на «Сегодня».
    // Новый фронт (если прилетел по Wi-Fi) подхватится при следующем запуске.
    fileprivate func reloadIfNeeded(_ view: WKWebView, _ coordinator: Coordinator) {
        if reloadToken != coordinator.lastReload {
            coordinator.lastReload = reloadToken
            view.evaluateJavaScript("window.pbSyncApplied && window.pbSyncApplied()", completionHandler: nil)
        }
    }
}
