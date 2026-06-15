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

        // Веб шлёт {action:'host'|'receive'} → запускаем синхрон, статус возвращаем в UI
        // через window.pbSync(текст); после применения снимка перезагружаем страницу.
        func userContentController(_ uc: WKUserContentController, didReceive message: WKScriptMessage) {
            guard message.name == "pipboySync" else { return }
            let action = (message.body as? [String: Any])?["action"] as? String ?? (message.body as? String) ?? ""
            sync.onStatus = { [weak self] s in
                let esc = s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "'", with: "\\'")
                self?.webView?.evaluateJavaScript("window.pbSync&&window.pbSync('\(esc)')", completionHandler: nil)
            }
            if action == "host" { sync.host() }
            else if action == "receive" { sync.receive() }
            else if action == "stop" { sync.stop(); sync.onStatus?("остановлено") }
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
            var top = scenes.flatMap { $0.windows }.first { $0.isKeyWindow }?.rootViewController
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
    // Перезагрузить страницу, когда reloadToken вырос (после применения снимка синхрона).
    fileprivate func reloadIfNeeded(_ view: WKWebView, _ coordinator: Coordinator) {
        if reloadToken != coordinator.lastReload {
            coordinator.lastReload = reloadToken
            view.reload()
        }
    }
}
