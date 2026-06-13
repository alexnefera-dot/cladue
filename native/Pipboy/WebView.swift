import SwiftUI
import WebKit

// Обёртка WKWebView — родной веб-движок Apple (не Chrome).
struct WebView: NSViewRepresentable {
    let url: URL
    func makeNSView(context: Context) -> WKWebView {
        let v = WKWebView()
        v.load(URLRequest(url: url))
        return v
    }
    func updateNSView(_ v: WKWebView, context: Context) {}
}
