import Foundation
import WebKit

// ЭТАП 1 — нативный слой чтения.
// WKURLSchemeHandler перехватывает запросы интерфейса (тот же фронт из app/public)
// и отдаёт статику + /api/* уже из ЗАШИФРОВАННОЙ базы, минуя Node.
// Подключается к WKWebView; включается флагом WebView.useNativeData (по умолчанию off,
// чтобы рабочее приложение продолжало ходить в Node, пока Swift не достигнет паритета).
final class PipboySchemeHandler: NSObject, WKURLSchemeHandler {
    static let scheme = "pipboy"

    // Все обращения к sqlite-соединению сериализуем — одно соединение, один поток.
    private let queue = DispatchQueue(label: "pipboy.nativeapi")
    private var db: Database?

    private func database() throws -> Database {
        if let db { return db }
        let made = try Database(key: try Keychain.databaseKey())
        db = made
        return made
    }

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        let url = task.request.url ?? URL(string: "pipboy://app/")!
        queue.async {
            do {
                let (data, mime, status) = try self.respond(to: url)
                let resp = HTTPURLResponse(url: url, statusCode: status, httpVersion: "HTTP/1.1",
                    headerFields: ["Content-Type": mime, "Cache-Control": "no-store"])!
                task.didReceive(resp)
                task.didReceive(data)
                task.didFinish()
            } catch {
                let body = "{\"error\":\"\(error)\"}".data(using: .utf8) ?? Data()
                let resp = HTTPURLResponse(url: url, statusCode: 500, httpVersion: "HTTP/1.1",
                    headerFields: ["Content-Type": "application/json"])!
                task.didReceive(resp); task.didReceive(body); task.didFinish()
            }
        }
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {}

    private func respond(to url: URL) throws -> (Data, String, Int) {
        let path = url.path.isEmpty ? "/" : url.path
        if path.hasPrefix("/api/") {
            let (data, status) = try Api.handle(path: path, query: url.query, db: try database())
            return (data, "application/json", status)
        }
        return try staticFile(path)
    }

    // Тот же фронт из репозитория app/public (host в pipboy://app/... игнорируем).
    private func staticFile(_ path: String) throws -> (Data, String, Int) {
        var rel = (path == "/") ? "index.html" : path
        if rel.hasPrefix("/") { rel.removeFirst() }
        let base = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Downloads/cladue/app/public", isDirectory: true)
        let file = base.appendingPathComponent(rel)
        let data = try Data(contentsOf: file)
        return (data, mime(file.pathExtension), 200)
    }

    private func mime(_ ext: String) -> String {
        switch ext.lowercased() {
        case "html": return "text/html; charset=utf-8"
        case "js", "mjs": return "text/javascript; charset=utf-8"
        case "css": return "text/css; charset=utf-8"
        case "json": return "application/json"
        case "svg": return "image/svg+xml"
        case "png": return "image/png"
        case "ico": return "image/x-icon"
        default: return "application/octet-stream"
        }
    }
}

// Роутер /api/* — пока ЧТЕНИЕ. Каждый эндпоинт = точный порт Node-ответа.
// Не реализованные пути дают 500 (в превью соответствующий экран будет пустым —
// это нормально, добиваем срезами: финансы, психология, дашборд, трекинг…).
enum Api {
    struct Unsupported: Error { let path: String }

    static func handle(path: String, query: String?, db: Database) throws -> (Data, Int) {
        switch path {
        case "/api/info":
            return (try json(["lan": NSNull(), "demoWiped": true, "version": "native"]), 200)
        case "/api/lock":
            return (try json(["enabled": try db.lockEnabled(), "localUnlock": true]), 200)
        case "/api/tree":
            return (try tree(db), 200)
        case "/api/pages":
            return (try json(try db.rows(
                "SELECT id, parent_id, ord, title, node_id, locked, updated_at FROM pages ORDER BY parent_id NULLS FIRST, ord, id")), 200)
        case "/api/trash":
            return (try json(try db.rows(
                "SELECT id, kind, label, created_at FROM trash ORDER BY id DESC LIMIT 30")), 200)
        case "/api/routines":
            return (try routines(db), 200)
        case "/api/routines/planned":
            return (try json(try db.rows("SELECT * FROM routines WHERE planned = 1 ORDER BY ord, id")), 200)
        case "/api/people":
            return (try people(db), 200)
        default:
            throw Unsupported(path: path)
        }
    }

    // /api/routines: активные рутины + отметка «сегодня» + стрик — порт life.listRoutines.
    static func routines(_ db: Database) throws -> Data {
        let done = Set(try db.rows("SELECT routine_id FROM routine_log WHERE date = ?", [localToday()])
            .compactMap { $0["routine_id"] as? Int })
        var rows = try db.rows("SELECT * FROM routines WHERE planned = 0 ORDER BY ord, id")
        for i in rows.indices {
            let id = rows[i]["id"] as? Int ?? -1
            rows[i]["done"] = done.contains(id)
            rows[i]["streak"] = try routineStreak(db, id)
        }
        return try json(rows)
    }

    static func routineStreak(_ db: Database, _ id: Int) throws -> Int {
        let dates = Set(try db.rows("SELECT date FROM routine_log WHERE routine_id = ?", [id])
            .compactMap { $0["date"] as? String })
        let f = localDateFormatter()
        let cal = Calendar.current
        var day = Date()
        if !dates.contains(f.string(from: day)) { day = cal.date(byAdding: .day, value: -1, to: day)! }
        var s = 0
        while s < 3650 && dates.contains(f.string(from: day)) {
            s += 1
            day = cal.date(byAdding: .day, value: -1, to: day)!
        }
        return s
    }

    // /api/people: ДР, контакт-ритм, связанные задачи, лог — порт life.listPeople.
    static func people(_ db: Database) throws -> Data {
        let today = ymdUTC.date(from: localToday()) ?? Date()
        let nodes = try db.rows("SELECT id, title FROM nodes WHERE is_category = 0 AND status IS NOT 'done'")
        var people = try db.rows("SELECT * FROM people ORDER BY name")
        for i in people.indices {
            let p = people[i]
            let name = (p["name"] as? String ?? "").lowercased()
            people[i]["days_to_birthday"] = daysToBirthday(p["birthday"] as? String)
            let rhythm = p["rhythm_days"] as? Int ?? 0
            let since: Int? = (p["last_contact"] as? String).flatMap { ymdUTC.date(from: $0) }
                .map { Int(floor(today.timeIntervalSince($0) / 86400)) }
            people[i]["since_contact"] = since ?? NSNull()
            if rhythm > 0, let since { people[i]["overdue_contact"] = max(0, since - rhythm) }
            else if rhythm > 0 { people[i]["overdue_contact"] = 1 }
            else { people[i]["overdue_contact"] = NSNull() }
            let pid = p["id"] as? Int ?? -1
            let tasks = nodes.filter { ($0["title"] as? String ?? "").lowercased().contains(name) }.prefix(3)
            people[i]["tasks"] = Array(tasks)
            people[i]["logs"] = try db.rows(
                "SELECT date, note FROM contact_log WHERE person_id = ? ORDER BY date DESC, id DESC LIMIT 3", [pid])
        }
        return try json(people)
    }

    // Дней до ближайшего ДР (UTC, как Date.parse в Node). nil → NSNull.
    private static func daysToBirthday(_ birthday: String?) -> Any {
        guard let b = birthday,
              let r = b.range(of: "[0-9]{2}-[0-9]{2}$", options: .regularExpression) else { return NSNull() }
        let parts = b[r].split(separator: "-")
        guard parts.count == 2, let m = Int(parts[0]), let d = Int(parts[1]) else { return NSNull() }
        var cal = Calendar(identifier: .gregorian); cal.timeZone = TimeZone(identifier: "UTC")!
        let c = cal.dateComponents([.year, .month, .day], from: Date())
        let todayUTC = cal.date(from: DateComponents(year: c.year, month: c.month, day: c.day))!
        var next = cal.date(from: DateComponents(year: c.year, month: m, day: d))!
        if next < todayUTC { next = cal.date(from: DateComponents(year: c.year! + 1, month: m, day: d))! }
        return Int((next.timeIntervalSince(todayUTC) / 86400).rounded())
    }

    // Локальная дата YYYY-MM-DD (сутки переключаются в твою полночь, как в Node).
    private static func localToday() -> String { localDateFormatter().string(from: Date()) }
    private static func localDateFormatter() -> DateFormatter {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }
    private static let ymdUTC: DateFormatter = {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"
        f.timeZone = TimeZone(identifier: "UTC"); f.locale = Locale(identifier: "en_US_POSIX")
        return f
    }()

    // /api/tree: все узлы (с флагом blocked) + связи — порт core.listTree.
    static func tree(_ db: Database) throws -> Data {
        let blockedRows = try db.rows("""
            SELECT DISTINCT l.to_id AS id FROM links l
            JOIN nodes p ON p.id = l.from_id
            WHERE l.type = 'blocks' AND NOT (p.status IN ('done','accepted'))
            """)
        let blocked = Set(blockedRows.compactMap { $0["id"] as? Int })
        var nodes = try db.rows("SELECT * FROM nodes ORDER BY parent_id NULLS FIRST, ord")
        for i in nodes.indices {
            let id = nodes[i]["id"] as? Int ?? -1
            nodes[i]["blocked"] = blocked.contains(id)
        }
        let links = try db.rows("SELECT * FROM links")
        return try json(["nodes": nodes, "links": links])
    }

    static func json(_ obj: Any) throws -> Data {
        try JSONSerialization.data(withJSONObject: obj, options: [])
    }
}
