import SwiftUI
import WebKit
import AppKit

// Обёртка WKWebView (родной движок Apple, не Chrome).
// Coordinator реализует WKUIDelegate — без него в WKWebView НЕ работают
// JS alert/confirm/prompt (молча проваливались: «Удалить?», «Очистить корзину?» и т.п.).
struct WebView: NSViewRepresentable {
    let url: URL

    // ЭТАП 1: источник данных интерфейса.
    //   false → Node (http://localhost:7777), рабочий режим;
    //   true  → нативный зашифрованный слой через pipboy:// (превью, читающие экраны).
    static let useNativeData = false

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeNSView(context: Context) -> WKWebView {
        // Мост для системных напоминаний: JS шлёт расписание в pipboyReminders.
        let cfg = WKWebViewConfiguration()
        cfg.userContentController.add(context.coordinator.notifier, name: "pipboyReminders")
        // Нативный слой данных: обработчик схемы pipboy:// (статика + /api/* из шифр-базы).
        cfg.setURLSchemeHandler(context.coordinator.scheme, forURLScheme: PipboySchemeHandler.scheme)
        let v = WKWebView(frame: .zero, configuration: cfg)
        v.uiDelegate = context.coordinator
        let start = Self.useNativeData ? URL(string: "pipboy://app/index.html")! : url
        v.load(URLRequest(url: start))
        return v
    }
    func updateNSView(_ v: WKWebView, context: Context) {}

    final class Coordinator: NSObject, WKUIDelegate {
        // Сильная ссылка на планировщик напоминаний (его держит и userContentController).
        let notifier = NotificationManager()
        // Обработчик нативного слоя данных (читает из зашифрованной базы).
        let scheme = PipboySchemeHandler()

        // alert(...)
        func webView(_ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping () -> Void) {
            let a = NSAlert(); a.messageText = "Pipboy"; a.informativeText = message
            a.addButton(withTitle: "OK"); a.runModal(); completionHandler()
        }
        // confirm(...) → true/false
        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping (Bool) -> Void) {
            let a = NSAlert(); a.messageText = "Pipboy"; a.informativeText = message
            a.addButton(withTitle: "OK"); a.addButton(withTitle: "Отмена")
            completionHandler(a.runModal() == .alertFirstButtonReturn)
        }
        // prompt(...) → текст или nil
        func webView(_ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String,
                     defaultText: String?, initiatedByFrame frame: WKFrameInfo,
                     completionHandler: @escaping (String?) -> Void) {
            let a = NSAlert(); a.messageText = "Pipboy"; a.informativeText = prompt
            a.addButton(withTitle: "OK"); a.addButton(withTitle: "Отмена")
            let field = NSTextField(frame: NSRect(x: 0, y: 0, width: 320, height: 24))
            field.stringValue = defaultText ?? ""
            a.accessoryView = field
            a.window.initialFirstResponder = field
            completionHandler(a.runModal() == .alertFirstButtonReturn ? field.stringValue : nil)
        }
        // Ссылки target="_blank" (ссылки внутри заметок Инфо). Без этого WKWebView
        // молча их игнорирует — клик по ссылке в заметке не открывал ничего.
        // Открываем во внешнем браузере, лишнее окно приложения не плодим.
        func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction,
                     windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let url = navigationAction.request.url { NSWorkspace.shared.open(url) }
            return nil
        }
    }
}
