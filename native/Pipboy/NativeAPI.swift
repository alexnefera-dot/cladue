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
        case "/api/psy":
            return (try json([
                "practices": try psyPractices(db),
                "wheel": try psyWheel(db),
                "worklog": try db.rows("SELECT * FROM work_log ORDER BY date DESC, id DESC LIMIT 20"),
                "decisions": try db.rows("""
                    SELECT id, title, answer, updated_at FROM nodes
                    WHERE kind = 'decision' AND status = 'accepted'
                    ORDER BY updated_at DESC LIMIT 30
                    """),
                "hasPass": try settingNonEmpty(db, "psy_pass_hash"),
            ]), 200)
        case "/api/track":
            return (try json([
                "checkins": try db.rows(
                    "SELECT * FROM checkins WHERE date >= date('now','localtime', ?) ORDER BY date DESC", ["-30 days"]),
                "metrics": try trackMetrics(db),
                "monthly": try trackMonthly(db),
            ]), 200)
        default:
            throw Unsupported(path: path)
        }
    }

    // /api/track → метрики с историей за 14 дней — порт life.listMetrics.
    static func trackMetrics(_ db: Database) throws -> [[String: Any]] {
        let t = localToday()
        var rows = try db.rows("SELECT * FROM metrics ORDER BY ord, id")
        for i in rows.indices {
            let id = rows[i]["id"] as? Int ?? -1
            let hist = try db.rows(
                "SELECT date, value FROM metric_log WHERE metric_id = ? AND date >= date('now','localtime', ?) ORDER BY date",
                [id, "-14 days"])
            rows[i]["history"] = hist
            rows[i]["today"] = hist.first(where: { ($0["date"] as? String) == t })?["value"] ?? NSNull()
            rows[i]["total"] = (try db.rows("SELECT count(*) AS c FROM metric_log WHERE metric_id = ?", [id])
                .first?["c"] as? Int) ?? 0
        }
        return rows
    }

    // Помесячная сводка за 6 месяцев — порт life.monthlyStats.
    static func trackMonthly(_ db: Database) throws -> [[String: Any]] {
        let defs = try db.rows("SELECT id, name, type, unit, polarity FROM metrics ORDER BY ord, id")
        let cal = Calendar.current
        var out: [[String: Any]] = []
        for i in 0..<6 {
            guard let d = cal.date(byAdding: .month, value: -i, to: Date()) else { continue }
            let c = cal.dateComponents([.year, .month], from: d)
            let ym = String(format: "%04d-%02d", c.year!, c.month!)
            var metrics: [[String: Any]] = []
            for mt in defs {
                let id = mt["id"] as? Int ?? -1
                let value: Any
                if (mt["type"] as? String) == "bool" {
                    let cnt = (try db.rows(
                        "SELECT count(*) AS v FROM metric_log WHERE metric_id = ? AND value > 0 AND substr(date,1,7) = ?",
                        [id, ym]).first?["v"] as? Int) ?? 0
                    value = cnt > 0 ? cnt : NSNull()
                } else {
                    let v = try db.rows(
                        "SELECT ROUND(AVG(value),1) AS v FROM metric_log WHERE metric_id = ? AND substr(date,1,7) = ?",
                        [id, ym]).first?["v"]
                    value = (v == nil || v is NSNull) ? NSNull() : v!
                }
                metrics.append([
                    "id": id, "name": mt["name"] ?? NSNull(), "type": mt["type"] ?? NSNull(),
                    "unit": mt["unit"] ?? NSNull(), "polarity": mt["polarity"] ?? NSNull(), "value": value,
                ])
            }
            let mood = try db.rows("SELECT ROUND(AVG(mood),1) AS v FROM checkins WHERE substr(date,1,7) = ?", [ym])
                .first?["v"] ?? NSNull()
            let tasksDone = (try db.rows("""
                SELECT count(*) AS c FROM nodes
                WHERE is_category = 0 AND status IN ('done','accepted') AND substr(updated_at,1,7) = ?
                """, [ym]).first?["c"] as? Int) ?? 0
            let routinesDone = (try db.rows("SELECT count(*) AS c FROM routine_log WHERE substr(date,1,7) = ?", [ym])
                .first?["c"] as? Int) ?? 0
            let empty = (mood is NSNull) && tasksDone == 0 && routinesDone == 0
                && metrics.allSatisfy { $0["value"] is NSNull }
            if i == 0 || !empty {
                out.append(["ym": ym, "metrics": metrics, "mood": mood,
                            "tasksDone": tasksDone, "routinesDone": routinesDone])
            }
        }
        return out
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

    // /api/psy → практики (steps/today/done/runs/streak) — порт psy.listPractices.
    static func psyPractices(_ db: Database) throws -> [[String: Any]] {
        let t = localToday()
        let doneToday = Set(try db.rows("SELECT practice_id FROM practice_log WHERE date = ?", [t])
            .compactMap { $0["practice_id"] as? Int })
        var rows = try db.rows("SELECT * FROM practices ORDER BY ord, id")
        for i in rows.indices {
            let id = rows[i]["id"] as? Int ?? -1
            let days = rows[i]["days"] as? String
            // steps хранится JSON-строкой → разбираем в массив
            if let s = rows[i]["steps"] as? String,
               let parsed = try? JSONSerialization.jsonObject(with: Data(s.utf8)) {
                rows[i]["steps"] = parsed
            } else { rows[i]["steps"] = [] }
            rows[i]["today"] = occursOn(days, t)
            rows[i]["done"] = doneToday.contains(id)
            rows[i]["runs"] = (try db.rows("SELECT count(*) AS c FROM practice_log WHERE practice_id = ?", [id])
                .first?["c"] as? Int) ?? 0
            rows[i]["streak"] = try practiceStreak(db, id: id, days: days)
        }
        return rows
    }

    // Колесо: сектора, даты замеров, последняя и предыдущая оценки — порт psy.wheel.
    static func psyWheel(_ db: Database) throws -> [String: Any] {
        let areas = try db.rows("SELECT * FROM wheel_areas ORDER BY ord, id")
        let dates = try db.rows("SELECT DISTINCT date FROM wheel_scores ORDER BY date DESC")
            .compactMap { $0["date"] as? String }
        func scores(_ date: String) throws -> [String: Any] {
            var m: [String: Any] = [:]
            for r in try db.rows("SELECT area_id, score FROM wheel_scores WHERE date = ?", [date]) {
                if let aid = r["area_id"] as? Int { m[String(aid)] = r["score"] ?? NSNull() }
            }
            return m
        }
        var out: [String: Any] = ["areas": areas, "dates": dates]
        out["latest"] = dates.indices.contains(0) ? ["date": dates[0], "scores": try scores(dates[0])] : NSNull()
        out["prev"] = dates.indices.contains(1) ? ["date": dates[1], "scores": try scores(dates[1])] : NSNull()
        return out
    }

    // Практика наступает сегодня? days = daily | workdays | "1,3,5" (Пн=1..Вс=7).
    private static func occursOn(_ days: String?, _ dateIso: String) -> Bool {
        guard let days, !days.isEmpty else { return false }
        if days == "daily" { return true }
        guard let date = localDateFormatter().date(from: dateIso) else { return false }
        let w = Calendar.current.component(.weekday, from: date)   // Вс=1..Сб=7
        let wd = ((w + 5) % 7) + 1                                  // Пн=1..Вс=7
        if days == "workdays" { return wd <= 5 }
        return days.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.contains(String(wd))
    }

    private static func practiceStreak(_ db: Database, id: Int, days: String?) throws -> Int {
        guard let days, !days.isEmpty else { return 0 }
        let dates = Set(try db.rows("SELECT date FROM practice_log WHERE practice_id = ?", [id])
            .compactMap { $0["date"] as? String })
        let f = localDateFormatter(); let cal = Calendar.current
        var d = Date()
        if occursOn(days, f.string(from: d)) && !dates.contains(f.string(from: d)) {
            d = cal.date(byAdding: .day, value: -1, to: d)!
        }
        var streak = 0
        for _ in 0..<365 {
            let day = f.string(from: d)
            if occursOn(days, day) {
                if !dates.contains(day) { break }
                streak += 1
            }
            d = cal.date(byAdding: .day, value: -1, to: d)!
        }
        return streak
    }

    private static func settingNonEmpty(_ db: Database, _ key: String) throws -> Bool {
        if let v = try db.rows("SELECT value FROM settings WHERE key = ?", [key]).first?["value"] as? String {
            return !v.isEmpty
        }
        return false
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
