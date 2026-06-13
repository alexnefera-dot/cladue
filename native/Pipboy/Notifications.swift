import Foundation
import UserNotifications
import WebKit

// Системные напоминания о рутинах.
// JS шлёт расписание через window.webkit.messageHandlers.pipboyReminders.postMessage(...):
//   { enabled: Bool, routines: [{ id, name, time:"HH:MM" }] }
// Планируем ежедневные ПОВТОРЯЮЩИЕСЯ пуши — они срабатывают, даже когда окно
// Pipboy закрыто (в отличие от Web Notifications, которых в WKWebView просто нет).
final class NotificationManager: NSObject, WKScriptMessageHandler {
    // Префикс наших идентификаторов — чтобы при пересинхронизации снимать только свои.
    private static let prefix = "routine-"

    // Приём расписания из JS.
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any] else { return }
        let enabled = (body["enabled"] as? Bool) ?? false
        let routines = (body["routines"] as? [[String: Any]]) ?? []
        if enabled {
            // Первый раз покажет системный запрос разрешения; дальше просто вернёт статус.
            UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { [weak self] _, _ in
                self?.reschedule(enabled: true, routines: routines)
            }
        } else {
            reschedule(enabled: false, routines: [])
        }
    }

    // Снимаем прежние напоминания Pipboy и ставим заново (идемпотентно).
    private func reschedule(enabled: Bool, routines: [[String: Any]]) {
        let center = UNUserNotificationCenter.current()
        center.getPendingNotificationRequests { reqs in
            let ours = reqs.map { $0.identifier }.filter { $0.hasPrefix(Self.prefix) }
            center.removePendingNotificationRequests(withIdentifiers: ours)
            guard enabled else { return }
            for r in routines {
                guard let name = r["name"] as? String, let time = r["time"] as? String else { continue }
                let id: String
                if let n = r["id"] as? Int { id = String(n) }
                else if let n = r["id"] as? Double { id = String(Int(n)) }
                else { continue }
                let parts = time.split(separator: ":")
                guard parts.count == 2, let h = Int(parts[0]), let m = Int(parts[1]) else { continue }
                var when = DateComponents(); when.hour = h; when.minute = m
                let content = UNMutableNotificationContent()
                content.title = "⏰ \(name)"
                content.body = "Рутина на \(time) — пора."
                content.sound = .default
                let trigger = UNCalendarNotificationTrigger(dateMatching: when, repeats: true)
                center.add(UNNotificationRequest(identifier: Self.prefix + id, content: content, trigger: trigger))
            }
        }
    }
}
