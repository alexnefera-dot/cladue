import Foundation
import UserNotifications
import WebKit

// Системные напоминания: рутины (ежедневно в ⏰) и события календаря (в дату/время).
// JS шлёт полное расписание через window.webkit.messageHandlers.pipboyReminders:
//   { enabled: Bool, items: [{ id, title, body, hour, minute, daily?, year?, month?, day? }] }
// Планируем UNCalendarNotificationTrigger — пуши срабатывают даже при закрытом окне,
// а делегат показывает их и когда Pipboy на переднем плане (со звуком).
final class NotificationManager: NSObject, WKScriptMessageHandler, UNUserNotificationCenterDelegate {
    override init() {
        super.init()
        UNUserNotificationCenter.current().delegate = self
    }

    // Приём расписания из JS.
    func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let body = message.body as? [String: Any] else { return }
        let enabled = (body["enabled"] as? Bool) ?? false
        let items = (body["items"] as? [[String: Any]]) ?? []
        if enabled {
            UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { [weak self] _, _ in
                self?.reschedule(items: items)
            }
        } else {
            reschedule(items: [])
        }
    }

    // Показывать баннер+звук, даже когда приложение активно.
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound, .list])
    }

    // Снимаем прежние наши напоминания и ставим заново (идемпотентно).
    private func reschedule(items: [[String: Any]]) {
        let center = UNUserNotificationCenter.current()
        center.getPendingNotificationRequests { reqs in
            let ours = reqs.map { $0.identifier }.filter { $0.hasPrefix("routine-") || $0.hasPrefix("event-") }
            center.removePendingNotificationRequests(withIdentifiers: ours)
            for it in items {
                guard let id = it["id"] as? String, let title = it["title"] as? String else { continue }
                let content = UNMutableNotificationContent()
                content.title = title
                content.body = (it["body"] as? String) ?? ""
                content.sound = .default
                var when = DateComponents()
                when.hour = Self.intOf(it["hour"]); when.minute = Self.intOf(it["minute"])
                let trigger: UNCalendarNotificationTrigger
                if (it["daily"] as? Bool) ?? false {
                    trigger = UNCalendarNotificationTrigger(dateMatching: when, repeats: true)
                } else {
                    when.year = Self.intOf(it["year"]); when.month = Self.intOf(it["month"]); when.day = Self.intOf(it["day"])
                    if let date = Calendar.current.date(from: when), date < Date() { continue }   // только будущее
                    trigger = UNCalendarNotificationTrigger(dateMatching: when, repeats: false)
                }
                center.add(UNNotificationRequest(identifier: id, content: content, trigger: trigger))
            }
        }
    }

    private static func intOf(_ v: Any?) -> Int {
        if let i = v as? Int { return i }
        if let d = v as? Double { return Int(d) }
        return 0
    }
}
