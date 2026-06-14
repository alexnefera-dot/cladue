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
        let method = task.request.httpMethod ?? "GET"
        // Тело POST/PATCH приходит в заголовке X-Pipboy-Body (WKURLSchemeHandler глотает httpBody).
        let bodyHeader = task.request.value(forHTTPHeaderField: "X-Pipboy-Body")
        queue.async {
            do {
                let (data, mime, status) = try self.respond(to: url, method: method, bodyHeader: bodyHeader)
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

    private func respond(to url: URL, method: String, bodyHeader: String?) throws -> (Data, String, Int) {
        let path = url.path.isEmpty ? "/" : url.path
        if path.hasPrefix("/api/") {
            NSLog("Pipboy native ← %@ %@", method, path)   // подтверждение: данные идут через pipboy://
            var body: [String: Any]? = nil
            if let raw = bodyHeader?.removingPercentEncoding, let d = raw.data(using: .utf8) {
                body = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any]
            }
            let (data, status) = try Api.handle(method: method, path: path, query: url.query, body: body, db: try database())
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

    static func handle(method: String, path: String, query: String?, body: [String: Any]?, db: Database) throws -> (Data, Int) {
        if method == "GET" { return try get(path: path, query: query, db: db) }
        return try write(method: method, path: path, body: body ?? [:], db: db)
    }

    static func get(path: String, query: String?, db: Database) throws -> (Data, Int) {
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
        case "/api/fin":
            return (try fin(db), 200)
        case "/api/fin/tx":
            let ym = queryValue(query, "month") ?? String(localToday().prefix(7))
            return (try json(try txMonth(db, ym)), 200)
        case "/api/calendar":
            let ym = queryValue(query, "month") ?? String(localToday().prefix(7))
            return (try json(try calendar(db, ym)), 200)
        case "/api/today":
            return (try todayDash(db), 200)
        default:
            throw Unsupported(path: path)
        }
    }

    // ===== ЗАПИСЬ (Этап 2). Пока — узлы целей; остальные разделы добавляем срезами. =====
    static func write(method: String, path: String, body: [String: Any], db: Database) throws -> (Data, Int) {
        if method == "POST", path == "/api/nodes" {
            guard let title = (body["title"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !title.isEmpty else { return (try json(["error": "title required"]), 400) }
            let parent = numOpt(body["parent_id"]).map { Int($0) }
            let id = try insertNode(db, parentId: parent, title: title, note: "",
                                    isCategory: intval(body["is_category"]) != 0 ? 1 : 0)
            return (try json(try getNode(db, id) ?? [:]), 201)
        }
        if let m = match(path, "^/api/nodes/([0-9]+)$") {
            let id = Int(m[1]) ?? -1
            if method == "PATCH" { return (try json(try updateNode(db, id: id, fields: body) ?? [:]), 200) }
            if method == "DELETE" { return (try json(try deleteNode(db, id: id)), 200) }
        }
        if let m = match(path, "^/api/nodes/([0-9]+)/toggle$"), method == "POST" {
            return (try json(try toggleNode(db, id: Int(m[1]) ?? -1) ?? [:]), 200)
        }
        if let m = match(path, "^/api/nodes/([0-9]+)/reorder$"), method == "POST" {
            guard let ref = numOpt(body["ref_id"]).map({ Int($0) }) else { return (try json(["error": "ref_id"]), 400) }
            let w = (body["where"] as? String) == "before" ? "before" : "after"
            do { return (try json(try reorderNode(db, id: Int(m[1]) ?? -1, refId: ref, where: w) ?? [:]), 200) }
            catch { return (try json(["error": "\(error)"]), 400) }
        }
        if let m = match(path, "^/api/nodes/([0-9]+)/move$"), method == "POST" {
            let parent = numOpt(body["parent_id"]).map { Int($0) }
            return (try json(try moveNode(db, id: Int(m[1]) ?? -1, newParent: parent) ?? [:]), 200)
        }
        throw Unsupported(path: "\(method) \(path)")
    }

    // ----- Узлы целей (порт core.js: insert/update/toggle/reorder/move/delete) -----
    private static let HOMO: [Character: Character] = ["а": "a", "е": "e", "о": "o", "с": "c", "р": "p",
        "х": "x", "у": "y", "к": "k", "в": "b", "м": "m", "т": "t"]
    private static func norm(_ s: String) -> String { String(s.lowercased().map { HOMO[$0] ?? $0 }) }
    private static let PATCHABLE = ["title", "note", "kind", "status", "priority", "due_date", "answer", "repeat"]

    static func getNode(_ db: Database, _ id: Int) throws -> [String: Any]? {
        try db.rows("SELECT * FROM nodes WHERE id = ?", [id]).first
    }

    static func insertNode(_ db: Database, parentId: Int?, title: String, note: String, isCategory: Int) throws -> Int {
        let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM nodes WHERE parent_id IS ?", [parentId]).first?["o"]))
        let id = try db.run("INSERT INTO nodes(parent_id, ord, title, note, is_category) VALUES(?,?,?,?,?)",
                            [parentId, ord, title, note, isCategory])
        try db.run("INSERT INTO node_fts(rowid, title_norm, note_norm) VALUES(?,?,?)", [id, norm(title), norm(note)])
        return id
    }

    static func updateNode(_ db: Database, id: Int, fields: [String: Any]) throws -> [String: Any]? {
        var f = fields
        var keys = PATCHABLE.filter { f[$0] != nil }
        if keys.isEmpty { return try getNode(db, id) }
        if keys.contains("kind") && f["status"] == nil {
            let kind = f["kind"] as? String
            f["status"] = kind == "decision" ? "open" : (kind == "task" ? "todo" : NSNull())
            keys.append("status")
        }
        let sets = keys.map { "\($0) = ?" }.joined(separator: ", ")
        var params: [Any?] = keys.map { f[$0] }
        params.append(id)
        try db.run("UPDATE nodes SET \(sets), updated_at = datetime('now') WHERE id = ?", params)
        if keys.contains("title") || keys.contains("note"), let t = try getNode(db, id) {
            try db.run("UPDATE node_fts SET title_norm = ?, note_norm = ? WHERE rowid = ?",
                       [norm(t["title"] as? String ?? ""), norm(t["note"] as? String ?? ""), id])
        }
        return try getNode(db, id)
    }

    static func addNodeLog(_ db: Database, nodeId: Int, note: String) throws {
        try db.run("INSERT INTO node_log(node_id, note, date) VALUES(?,?,date('now','localtime'))", [nodeId, note])
    }

    static func toggleNode(_ db: Database, id: Int) throws -> [String: Any]? {
        guard let t = try getNode(db, id) else { return nil }
        let kind = t["kind"] as? String
        guard kind == "task" || kind == "decision" else { return t }
        let status = t["status"] as? String
        let next = kind == "decision" ? (status == "open" ? "accepted" : "open")
                                      : (status == "done" ? "todo" : "done")
        if next == "done", kind == "task",
           let rep = t["repeat"] as? String, !rep.isEmpty, let due = t["due_date"] as? String {
            try addNodeLog(db, nodeId: id, note: "✓ выполнено (повтор \(rep))")
            var n = try updateNode(db, id: id, fields: ["due_date": shiftRepeat(due, rep)]) ?? [:]
            n["repeated"] = true
            return n
        }
        let res = try updateNode(db, id: id, fields: ["status": next])
        try db.run("UPDATE steps SET status = ? WHERE task_id = ?", [next == "done" ? "done" : "planned", id])
        return res
    }

    private static func shiftRepeat(_ iso: String, _ rep: String) -> String {
        if rep == "weekly", let d = ymdUTC.date(from: iso) {
            return ymdUTC.string(from: d.addingTimeInterval(7 * 86400))
        }
        return addMonths(iso, rep == "yearly" ? 12 : 1)
    }

    static func reorderNode(_ db: Database, id: Int, refId: Int, where w: String) throws -> [String: Any]? {
        if id == refId { throw Unsupported(path: "self") }
        guard let ref = try db.rows("SELECT id, parent_id FROM nodes WHERE id = ?", [refId]).first else {
            throw Unsupported(path: "ref not found")
        }
        let refParent = numOpt(ref["parent_id"]).map { Int($0) }
        if refParent == id { throw Unsupported(path: "descendant") }
        if let rp = refParent {
            let desc = try db.rows("""
                WITH RECURSIVE r(x) AS (
                  SELECT id FROM nodes WHERE parent_id = ?
                  UNION SELECT n.id FROM nodes n JOIN r ON n.parent_id = r.x
                ) SELECT 1 FROM r WHERE x = ? LIMIT 1
                """, [id, rp])
            if !desc.isEmpty { throw Unsupported(path: "descendant") }
        }
        var siblings = try db.rows("SELECT id FROM nodes WHERE parent_id IS ? ORDER BY ord, id", [refParent])
            .compactMap { $0["id"] as? Int }.filter { $0 != id }
        if let idx = siblings.firstIndex(of: refId) { siblings.insert(id, at: idx + (w == "after" ? 1 : 0)) }
        else { siblings.append(id) }
        try db.run("UPDATE nodes SET parent_id = ?, updated_at = datetime('now') WHERE id = ?", [refParent, id])
        for (i, sid) in siblings.enumerated() { try db.run("UPDATE nodes SET ord = ? WHERE id = ?", [i + 1, sid]) }
        return try getNode(db, id)
    }

    static func moveNode(_ db: Database, id: Int, newParent: Int?) throws -> [String: Any]? {
        if let np = newParent {
            if np == id { throw Unsupported(path: "self-parent") }
            let desc = try db.rows("""
                WITH RECURSIVE r(x) AS (
                  SELECT id FROM nodes WHERE parent_id = ?
                  UNION SELECT n.id FROM nodes n JOIN r ON n.parent_id = r.x
                ) SELECT 1 FROM r WHERE x = ? LIMIT 1
                """, [id, np])
            if !desc.isEmpty { throw Unsupported(path: "descendant") }
        }
        let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM nodes WHERE parent_id IS ?", [newParent]).first?["o"]))
        try db.run("UPDATE nodes SET parent_id = ?, ord = ?, updated_at = datetime('now') WHERE id = ?", [newParent, ord, id])
        return try getNode(db, id)
    }

    static func deleteNode(_ db: Database, id: Int) throws -> [String: Any] {
        guard let root = try getNode(db, id) else { return ["count": 0, "trash_id": NSNull()] }
        let rows = try db.rows("""
            WITH RECURSIVE r(x, depth) AS (
              SELECT ?, 0 UNION ALL
              SELECT n.id, r.depth + 1 FROM nodes n JOIN r ON n.parent_id = r.x
            ) SELECT n.*, r.depth AS _depth FROM r JOIN nodes n ON n.id = r.x ORDER BY r.depth, n.ord
            """, [id])
        let ids = Set(rows.compactMap { $0["id"] as? Int })
        let links = try db.rows("SELECT * FROM links")
            .filter { ids.contains(intval($0["from_id"])) || ids.contains(intval($0["to_id"])) }
        let stepRefs = try db.rows("SELECT id AS step_id, task_id FROM steps WHERE task_id IS NOT NULL")
            .filter { ids.contains(intval($0["task_id"])) }
        let label = (root["title"] as? String ?? "") + (rows.count > 1 ? " (+\(rows.count - 1) влож.)" : "")
        let payload = String(data: try json(["rows": rows, "links": links, "stepRefs": stepRefs]), encoding: .utf8) ?? "{}"
        let trashId = try db.run("INSERT INTO trash(kind, label, payload) VALUES(?,?,?)", ["nodes", label, payload])
        for x in ids {
            try db.run("DELETE FROM node_fts WHERE rowid = ?", [x])
            try db.run("UPDATE steps SET task_id = NULL WHERE task_id = ?", [x])
        }
        try db.run("DELETE FROM nodes WHERE id = ?", [id])
        return ["count": rows.count, "trash_id": trashId]
    }

    private static func match(_ s: String, _ pattern: String) -> [String]? {
        guard let re = try? NSRegularExpression(pattern: pattern),
              let m = re.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) else { return nil }
        return (0..<m.numberOfRanges).map { i in
            Range(m.range(at: i), in: s).map { String(s[$0]) } ?? ""
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

    // ===== Финансы (порт fin.listFin/portfolioTree/eurUsdRate и помощников) =====

    // Курс EURUSD: долларов за 1 евро (дефолт 1.08).
    static func eurUsdRate(_ db: Database) throws -> Double {
        let v = num(try db.rows("SELECT price FROM rates WHERE symbol = 'EURUSD'").first?["price"])
        return v != 0 ? v : 1.08
    }

    // Дерево портфеля: листья — в родной валюте, агрегаты — в € по курсу.
    static func portfolioTree(_ db: Database) throws -> [[String: Any]] {
        let rate = try eurUsdRate(db)
        let toEur: (Double?, String?) -> Double? = { v, cur in
            guard let v else { return nil }
            return cur == "$" ? v / rate : v
        }
        var prices: [String: Double] = [:]
        for r in try db.rows("SELECT symbol, price FROM rates") {
            if let s = r["symbol"] as? String { prices[s] = num(r["price"]) }
        }
        var rows: [[String: Any]] = []
        for var r in try db.rows("SELECT * FROM portfolio_items ORDER BY parent_id NULLS FIRST, ord, id") {
            if let sym = r["rate_symbol"] as? String, numOpt(r["qty"]) != nil {
                if let price = prices[sym] {
                    r["value"] = num(r["qty"]) * price; r["currency"] = "$"; r["auto"] = true
                } else { r["no_rate"] = true }
            }
            rows.append(r)
        }
        var byParent: [String: [[String: Any]]] = [:]
        for r in rows {
            let key = numOpt(r["parent_id"]) == nil ? "root" : String(intval(r["parent_id"]))
            byParent[key, default: []].append(r)
        }
        return (byParent["root"] ?? []).map { calcNode($0, byParent, toEur) }
    }

    private static func calcNode(_ r: [String: Any], _ byParent: [String: [[String: Any]]],
                                 _ toEur: (Double?, String?) -> Double?) -> [String: Any] {
        var node = r
        let children = (byParent[String(intval(r["id"]))] ?? []).map { calcNode($0, byParent, toEur) }
        let isLeaf = (r["kind"] as? String) == "asset" || children.isEmpty
        let value = numOpt(r["value"]); let cur = r["currency"] as? String
        func sum(_ key: String) -> Double { children.reduce(0.0) { $0 + ($1[key] as? Double ?? 0) } }
        func anyNonNull(_ key: String) -> Bool { children.contains { ($0[key] as? Double) != nil } }
        let eur = isLeaf ? (toEur(value, cur) ?? 0) : sum("eur")
        let usdPart = isLeaf ? (cur == "$" ? (value ?? 0) : 0) : sum("usdPart")
        let eurPart = isLeaf ? (cur != "$" ? (value ?? 0) : 0) : sum("eurPart")
        let buyEff = numOpt(r["buy_value"]) ?? value
        let invested: Double? = isLeaf ? (buyEff != nil ? (toEur(buyEff, cur) ?? 0) : nil)
            : (anyNonNull("invested") ? sum("invested") : nil)
        let investedCur: Double? = isLeaf ? (value != nil ? (toEur(value, cur) ?? 0) : nil)
            : (anyNonNull("investedCur") ? sum("investedCur") : nil)
        let target: Double? = numOpt(r["target_value"]) ?? (anyNonNull("target") ? sum("target") : nil)
        node["children"] = children
        node["eur"] = eur; node["usdPart"] = usdPart; node["eurPart"] = eurPart
        node["value"] = isLeaf ? (r["value"] ?? NSNull()) : eur
        node["invested"] = invested ?? NSNull()
        node["investedCur"] = investedCur ?? NSNull()
        node["target"] = target ?? NSNull()
        return node
    }

    static func fin(_ db: Database) throws -> Data {
        let rate = try eurUsdRate(db)
        let t = localToday()
        var accounts = try db.rows("SELECT * FROM accounts ORDER BY id")
        for i in accounts.indices {
            let bu = (accounts[i]["balance_updated_at"] as? String).map { String($0.prefix(10)) }
            accounts[i]["stale_days"] = bu.flatMap { dayDiff($0, t) }.map { Int(floor($0)) } ?? 0
        }
        let portfolio = try portfolioTree(db)
        let portfolioTotal = portfolio.reduce(0.0) { $0 + ($1["eur"] as? Double ?? 0) }
        let portfolioTotalUsd = portfolioTotal * rate
        let invested = portfolio.reduce(0.0) { $0 + ($1["invested"] as? Double ?? 0) }
        let investedCur = portfolio.reduce(0.0) { $0 + ($1["investedCur"] as? Double ?? 0) }
        let steps = try db.rows("SELECT * FROM steps ORDER BY status = 'done', planned_date IS NULL, planned_date, id")
        var obligations = try db.rows("SELECT * FROM obligations ORDER BY next_date IS NULL, next_date")
        for i in obligations.indices {
            obligations[i]["days_left"] = (obligations[i]["next_date"] as? String)
                .flatMap { dayDiff(t, $0) }.map { Int(ceil($0)) } ?? NSNull()
        }
        var byCur: [String: Double] = [:]
        for a in accounts { byCur[a["currency"] as? String ?? "", default: 0] += num(a["balance"]) }
        // займы — зеркало активов с флагом is_loan
        var loans: [[String: Any]] = []
        func walkLoan(_ n: [String: Any], _ path: [String]) {
            let children = n["children"] as? [[String: Any]] ?? []
            let isLeaf = (n["kind"] as? String) == "asset" || children.isEmpty
            if intval(n["is_loan"]) != 0 && isLeaf {
                let due = n["loan_due"] as? String
                loans.append([
                    "id": n["id"] ?? NSNull(), "name": n["name"] ?? NSNull(),
                    "value": n["value"] ?? NSNull(), "currency": (n["currency"] as? String) ?? "€",
                    "loan_due": due ?? NSNull(), "path": path.joined(separator: " → "),
                    "overdue_days": due.flatMap { dayDiff($0, t) }.map { Int(floor($0)) } ?? NSNull(),
                ])
            }
            for c in children { walkLoan(c, path + [n["name"] as? String ?? ""]) }
        }
        for b in portfolio { walkLoan(b, []) }
        // аллокация по типам активов
        var byType: [String: Double] = [:]
        var byTypeBlocks: [String: [String: Double]] = [:]
        func walkType(_ n: [String: Any], _ rootName: String) {
            let children = n["children"] as? [[String: Any]] ?? []
            let isLeaf = (n["kind"] as? String) == "asset" || children.isEmpty
            if isLeaf, let e = n["eur"] as? Double, e != 0 {
                let ty = n["asset_type"] as? String ?? "без типа"
                byType[ty, default: 0] += e
                byTypeBlocks[ty, default: [:]][rootName, default: 0] += e
            }
            for c in children { walkType(c, rootName) }
        }
        for b in portfolio { walkType(b, b["name"] as? String ?? "") }
        var blockEur: [String: Any] = [:]
        for b in portfolio { blockEur[b["name"] as? String ?? ""] = b["eur"] ?? 0 }
        var debts = try db.rows("SELECT * FROM debts ORDER BY due_date IS NULL, due_date")
        for i in debts.indices {
            debts[i]["overdue_days"] = (debts[i]["due_date"] as? String)
                .flatMap { dayDiff($0, t) }.map { Int(floor($0)) } ?? NSNull()
        }
        let snaps = try db.rows("SELECT * FROM snapshots ORDER BY date DESC LIMIT 2")
        let snapshotDelta: Any = snaps.count == 2
            ? ["since": snaps[1]["date"] ?? NSNull(),
               "abs": num(snaps[0]["portfolio_eur"]) - num(snaps[1]["portfolio_eur"])]
            : NSNull()
        let income = try db.rows("SELECT * FROM passive_income ORDER BY period, id")
        let monthlyIncome = income.reduce(0.0) { acc, i in
            let eur = (i["currency"] as? String) == "$" ? num(i["amount"]) / rate : num(i["amount"])
            let p = i["period"] as? String
            return acc + (p == "monthly" ? eur : p == "yearly" ? eur / 12 : 0)
        }
        let monthlyObligations = obligations.filter { ($0["period"] as? String) == "monthly" }
            .reduce(0.0) { $0 + num($1["amount"]) }
        let upcoming = obligations.filter { ($0["days_left"] as? Int).map { $0 <= 30 } ?? false }
        let budgetStr = try db.rows("SELECT value FROM settings WHERE key = 'monthly_budget'").first?["value"] as? String
        let budget: Any = budgetStr.flatMap { Double($0) }.flatMap { $0 != 0 ? $0 : nil } ?? NSNull()
        let growth: Any = invested != 0
            ? ["invested": invested, "current": investedCur,
               "abs": investedCur - invested, "pct": (investedCur - invested) / invested * 100]
            : NSNull()
        let byTypeSorted: [[Any]] = byType.sorted { $0.value > $1.value }.map { [$0.key, $0.value] }
        let summary: [String: Any] = [
            "accountsByCurrency": byCur,
            "portfolioTotal": portfolioTotal, "portfolioTotalUsd": portfolioTotalUsd, "rate": rate,
            "growth": growth, "monthlyObligations": monthlyObligations,
            "monthlyIncome": monthlyIncome, "upcoming": upcoming,
        ]
        let tx = try txMonth(db, String(t.prefix(7)))
        let fc = try forecasts(db)
        let props = try properties(db)
        let fireV = try fireCalc(db, capital: portfolioTotal)
        let macro = try db.rows("SELECT * FROM macro_notes ORDER BY date DESC, id DESC")
        let rates = try db.rows("SELECT * FROM rates")
        let result: [String: Any] = [
            "accounts": accounts, "portfolio": portfolio, "steps": steps,
            "obligations": obligations, "loans": loans, "debts": debts,
            "snapshotDelta": snapshotDelta,
            "byType": byTypeSorted, "byTypeBlocks": byTypeBlocks, "blockEur": blockEur,
            "tx": tx, "forecasts": fc, "properties": props, "fire": fireV,
            "income": income, "budget": budget, "macro": macro, "rates": rates,
            "summary": summary,
        ]
        return try json(result)
    }

    static func txMonth(_ db: Database, _ ym: String) throws -> [String: Any] {
        let rows = try db.rows("SELECT * FROM transactions WHERE date LIKE ? ORDER BY date DESC, id DESC", [ym + "%"])
        func sumDir(_ dir: String) -> Double {
            rows.filter { ($0["direction"] as? String) == dir }.reduce(0.0) { $0 + num($1["amount"]) }
        }
        var byCat: [String: Double] = [:]
        for tx in rows where (tx["direction"] as? String) == "expense" {
            byCat[tx["category"] as? String ?? "", default: 0] += num(tx["amount"])
        }
        return ["month": ym, "rows": rows, "expense": sumDir("expense"), "income": sumDir("income"),
                "categories": byCat.sorted { $0.value > $1.value }.map { [$0.key, $0.value] as [Any] }]
    }

    static func fireCalc(_ db: Database, capital: Double) throws -> [String: Any] {
        func setting(_ k: String, _ def: Double) throws -> Double {
            if let v = try db.rows("SELECT value FROM settings WHERE key = ?", [k]).first?["value"] as? String,
               let d = Double(v) { return d }
            return def
        }
        let target = try setting("fire_target", 0)
        let annual = try setting("fire_return_pct", 5)
        let monthly = try setting("fire_monthly_savings", 0)
        if target == 0 { return ["target": 0] }
        let r = pow(1 + annual / 100, 1.0 / 12) - 1
        var cap = capital, months = 0
        while cap < target && months < 1200 { cap = cap * (1 + r) + monthly; months += 1 }
        let cal = Calendar.current; let now = Date()
        let curMonth = cal.component(.month, from: now) - 1
        let curYear = cal.component(.year, from: now)
        return [
            "target": target, "annual": annual, "monthly": monthly,
            "progressPct": min(100, capital / target * 100),
            "months": months >= 1200 ? NSNull() : months,
            "reachedYear": months >= 1200 ? NSNull() : curYear + Int(floor(Double(curMonth + months) / 12)),
        ]
    }

    static func forecasts(_ db: Database) throws -> [String: Any] {
        let rows = try db.rows("SELECT * FROM forecasts ORDER BY outcome IS NOT NULL, due_date IS NULL, due_date, id DESC")
        let resolved = rows.filter { ($0["outcome"] as? Double) != nil || ($0["outcome"] as? Int) != nil }
        let calibration: Any = resolved.isEmpty ? NSNull()
            : 100 - resolved.reduce(0.0) { $0 + abs(num($1["confidence"]) - num($1["outcome"]) * 100) } / Double(resolved.count)
        return ["rows": rows, "calibration": calibration, "resolvedCount": resolved.count]
    }

    static func properties(_ db: Database) throws -> [[String: Any]] {
        let t = localToday()
        var props = try db.rows("SELECT * FROM properties ORDER BY category, name")
        for i in props.indices {
            var rules = try db.rows(
                "SELECT * FROM obligations WHERE property_id = ? ORDER BY next_date IS NULL, next_date",
                [intval(props[i]["id"])])
            for j in rules.indices {
                rules[j]["days_left"] = (rules[j]["next_date"] as? String)
                    .flatMap { dayDiff(t, $0) }.map { Int(ceil($0)) } ?? NSNull()
            }
            props[i]["rules"] = rules
        }
        return props
    }

    // ===== Календарь (порт cal.calendar + occurrences/birthdays) =====
    static func calendar(_ db: Database, _ ym: String) throws -> [String: Any] {
        guard ym.range(of: "^[0-9]{4}-[0-9]{2}$", options: .regularExpression) != nil,
              let y = Int(ym.prefix(4)), let m = Int(ym.suffix(2)) else {
            throw Unsupported(path: "calendar:\(ym)")
        }
        var cal = Calendar(identifier: .gregorian); cal.timeZone = TimeZone(identifier: "UTC")!
        let first = ym + "-01"
        let lastDay = cal.range(of: .day, in: .month,
            for: cal.date(from: DateComponents(year: y, month: m, day: 1))!)!.count
        let last = ym + "-" + String(format: "%02d", lastDay)
        var items: [[String: Any]] = []
        for t in try db.rows("""
            SELECT id, title, kind, status, priority, due_date FROM nodes
            WHERE due_date BETWEEN ? AND ? AND kind IN ('task','decision')
            """, [first, last]) {
            let st = t["status"] as? String ?? ""
            items.append(["date": t["due_date"] ?? NSNull(), "type": "task", "id": t["id"] ?? NSNull(),
                "title": t["title"] ?? NSNull(), "done": ["done", "accepted"].contains(st),
                "kind": t["kind"] ?? NSNull(), "priority": t["priority"] ?? NSNull()])
        }
        for s in try db.rows("SELECT * FROM steps WHERE planned_date BETWEEN ? AND ? AND task_id IS NULL", [first, last]) {
            let kind = s["kind"] as? String ?? ""
            let label = ["buy": "Купить", "sell": "Продать", "transfer": "Перевод"][kind] ?? kind
            items.append(["date": s["planned_date"] ?? NSNull(), "type": "step", "id": s["id"] ?? NSNull(),
                "title": label + ": " + (s["title"] as? String ?? ""),
                "done": (s["status"] as? String) == "done", "amount": s["amount"] ?? NSNull()])
        }
        for o in try db.rows("SELECT * FROM obligations WHERE next_date IS NOT NULL") {
            let recur = (o["period"] as? String) == "once" ? "none" : (o["period"] as? String)
            for d in occurrences(o["next_date"] as? String, recur, first, last) {
                items.append(["date": d, "type": "money", "id": o["id"] ?? NSNull(), "title": o["name"] ?? NSNull(),
                    "amount": o["amount"] ?? NSNull(), "currency": o["currency"] ?? NSNull(), "okind": o["kind"] ?? NSNull()])
            }
        }
        for e in try db.rows("SELECT * FROM events") {
            for d in occurrences(e["date"] as? String, e["recur"] as? String, first, last) {
                items.append(["date": d, "type": "event", "id": e["id"] ?? NSNull(), "title": e["title"] ?? NSNull(),
                    "time": e["time"] ?? NSNull(), "recur": e["recur"] ?? NSNull()])
            }
        }
        for p in try birthdays(db) {
            let md = p["mmdd"] as? String ?? ""
            let d = ym + "-" + String(md.suffix(2))
            if String(md.prefix(2)) == String(ym.suffix(2)) && d >= first && d <= last {
                items.append(["date": d, "type": "event", "id": "p\(intval(p["id"]))",
                    "title": "🎂 " + (p["name"] as? String ?? ""), "recur": "yearly", "bday": true])
            }
        }
        items.sort { a, b in
            let da = a["date"] as? String ?? "", dbb = b["date"] as? String ?? ""
            if da != dbb { return da < dbb }
            return (a["time"] as? String ?? "") < (b["time"] as? String ?? "")
        }
        return ["month": ym, "first": first, "last": last, "items": items]
    }

    // Развёртка повторов: список дат вхождения в [first, last] (ISO-строки сравниваются лексикографически).
    private static func occurrences(_ startDate: String?, _ recur: String?, _ first: String, _ last: String) -> [String] {
        guard let startDate, !startDate.isEmpty else { return [] }
        if recur == nil || recur == "none" || recur == "" {
            return (startDate >= first && startDate <= last) ? [startDate] : []
        }
        var out: [String] = []; var d = startDate; var i = 0
        while i < 2700 && d <= last {
            if d >= first { out.append(d) }
            if recur == "weekly", let dt = ymdUTC.date(from: d) {
                d = ymdUTC.string(from: dt.addingTimeInterval(7 * 86400))
            } else {
                d = addMonths(d, recur == "yearly" ? 12 : 1)
            }
            i += 1
        }
        return out
    }

    private static func addMonths(_ iso: String, _ months: Int) -> String {
        var cal = Calendar(identifier: .gregorian); cal.timeZone = TimeZone(identifier: "UTC")!
        guard let d = ymdUTC.date(from: String(iso.prefix(10))),
              let r = cal.date(byAdding: .month, value: months, to: d) else { return iso }
        return ymdUTC.string(from: r)
    }

    private static func birthdays(_ db: Database) throws -> [[String: Any]] {
        var out: [[String: Any]] = []
        for p in try db.rows("SELECT id, name, birthday FROM people WHERE birthday IS NOT NULL") {
            if let b = p["birthday"] as? String,
               let r = b.range(of: "[0-9]{2}-[0-9]{2}$", options: .regularExpression) {
                out.append(["id": p["id"] ?? NSNull(), "name": p["name"] ?? NSNull(), "mmdd": String(b[r])])
            }
        }
        return out
    }

    // Вхождения практик за месяц (для дашборда) — порт psy.monthOccurrences.
    static func monthOccurrences(_ db: Database, _ ym: String, _ first: String, _ last: String) throws -> [[String: Any]] {
        var items: [[String: Any]] = []
        let logged = Set(try db.rows("SELECT practice_id, date FROM practice_log WHERE date BETWEEN ? AND ?", [first, last])
            .compactMap { l -> String? in
                guard let pid = l["practice_id"] as? Int, let d = l["date"] as? String else { return nil }
                return "\(pid):\(d)"
            })
        for p in try db.rows("SELECT * FROM practices WHERE days != ''") {
            let days = p["days"] as? String
            for day in 1...31 {
                let date = ym + "-" + String(format: "%02d", day)
                if date < first || date > last { continue }
                if occursOn(days, date) {
                    items.append(["date": date, "type": "practice", "id": p["id"] ?? NSNull(),
                        "title": p["name"] ?? NSNull(), "time": p["time"] ?? NSNull(),
                        "done": logged.contains("\(intval(p["id"])):\(date)")])
                }
            }
        }
        return items
    }

    // ===== Дашборд «Сегодня» (порт today.buildToday + movement/sortRoutines) =====
    static func todayDash(_ db: Database) throws -> Data {
        let t = localToday()
        let cal = Calendar.current
        let tomorrow = localDateFormatter().string(from: cal.date(byAdding: .day, value: 1, to: Date())!)
        let weekEnd = localDateFormatter().string(from: cal.date(byAdding: .day, value: 7, to: Date())!)
        func taskRows(_ cond: String) throws -> [[String: Any]] {
            try db.rows("""
                SELECT id, title, kind, priority, due_date, repeat FROM nodes
                WHERE kind IN ('task','decision') AND status IN ('todo','open') AND \(cond)
                ORDER BY priority IS NULL, priority, due_date
                """, [t])
        }
        let overdue = try taskRows("due_date < ?")
        let dueToday = try taskRows("due_date = ?")
        // лента: текущий + следующий месяц, без дублей
        let ym = String(t.prefix(7))
        let nextYm = String(addMonths(ym + "-01", 1).prefix(7))
        var seen = Set<String>(); var all: [[String: Any]] = []
        for src in [try calendar(db, ym), try calendar(db, nextYm)] {
            for i in (src["items"] as? [[String: Any]]) ?? [] {
                let key = "\(i["type"] ?? ""):\(i["id"] ?? ""):\(i["date"] ?? "")"
                if seen.insert(key).inserted { all.append(i) }
            }
        }
        func dateOf(_ i: [String: Any]) -> String { i["date"] as? String ?? "" }
        let week = all.filter { dateOf($0) > t && dateOf($0) <= weekEnd && !(($0["done"] as? Bool) ?? false) }
        let events = all.filter { ($0["type"] as? String) == "event" && (dateOf($0) == t || dateOf($0) == tomorrow) }
        let payments7 = all.filter { ($0["type"] as? String) == "money" && dateOf($0) >= t && dateOf($0) <= weekEnd }
        // финансы → просроченные долги/займы
        let finObj = (try? JSONSerialization.jsonObject(with: try fin(db))) as? [String: Any] ?? [:]
        var debtsOverdue = (finObj["debts"] as? [[String: Any]] ?? [])
            .filter { ($0["overdue_days"] as? Int).map { $0 > 0 } ?? false }
        for l in (finObj["loans"] as? [[String: Any]] ?? []) where (l["overdue_days"] as? Int).map({ $0 > 0 }) ?? false {
            debtsOverdue.append(["id": "loan\(intval(l["id"]))", "name": (l["name"] as? String ?? "") + " (займ из портфеля)",
                "amount": l["value"] ?? NSNull(), "currency": l["currency"] ?? NSNull(),
                "direction": "owed_to_me", "overdue_days": l["overdue_days"] ?? NSNull()])
        }
        // люди → ближайшие ДР и просроченные контакты
        let peopleArr = (try? JSONSerialization.jsonObject(with: try people(db))) as? [[String: Any]] ?? []
        let bdays = peopleArr.filter { ($0["days_to_birthday"] as? Int).map { $0 <= 30 } ?? false }
            .sorted { ($0["days_to_birthday"] as? Int ?? 0) < ($1["days_to_birthday"] as? Int ?? 0) }.prefix(5)
        let overdueContacts = peopleArr.filter { ($0["overdue_contact"] as? Int).map { $0 > 0 } ?? false }
            .sorted { ($0["overdue_contact"] as? Int ?? 0) > ($1["overdue_contact"] as? Int ?? 0) }.prefix(5)
        // недельные цели (пн–вс)
        let now = Date()
        let wd = (cal.component(.weekday, from: now) + 5) % 7   // 0=Пн..6=Вс
        let monday = localDateFormatter().string(from: cal.date(byAdding: .day, value: -wd, to: now)!)
        let sunday = localDateFormatter().string(from: cal.date(byAdding: .day, value: 6 - wd, to: now)!)
        let wg = try db.rows("""
            SELECT count(*) AS total, SUM(CASE WHEN status IN ('done','accepted') THEN 1 ELSE 0 END) AS done
            FROM nodes WHERE kind IN ('task','decision') AND due_date BETWEEN ? AND ?
            """, [monday, sunday]).first
        let checkin = try db.rows("SELECT mood, note FROM checkins WHERE date = ?", [t]).first
        let real = (try db.rows("SELECT count(*) AS c FROM nodes WHERE is_category = 0").first?["c"] as? Int) ?? 0
        let typed = (try db.rows("SELECT count(*) AS c FROM nodes WHERE is_category = 0 AND kind IS NOT NULL").first?["c"] as? Int) ?? 0
        let inboxCat = try db.rows("SELECT id FROM nodes WHERE is_category = 1 AND title LIKE '%Инбокс%'").first
        let inboxId = inboxCat.map { intval($0["id"]) }
        let inbox = inboxId != nil
            ? ((try db.rows("SELECT count(*) AS c FROM nodes WHERE parent_id = ?", [inboxId!]).first?["c"] as? Int) ?? 0) : 0
        let practicesToday = (try monthOccurrences(db, ym, t, t))
            .filter { dateOf($0) == t && !(($0["done"] as? Bool) ?? false) }.count
        let routinesArr = (try? JSONSerialization.jsonObject(with: try routines(db))) as? [[String: Any]] ?? []
        let result: [String: Any] = [
            "date": t,
            "activityMonth": (try db.rows("SELECT value FROM settings WHERE key = 'activity_month'").first?["value"]) ?? NSNull(),
            "routines": sortRoutines(routinesArr),
            "overdue": overdue, "dueToday": dueToday, "week": week, "events": events,
            "zones": ["paymentsWeek": payments7.count, "debtsOverdue": debtsOverdue.count, "practicesToday": practicesToday],
            "people": ["birthdays": Array(bdays), "overdueContacts": Array(overdueContacts)],
            "movement": try movement(db),
            "weekGoals": ["total": (wg?["total"] as? Int) ?? 0, "done": (wg?["done"] as? Int) ?? 0],
            "checkin": checkin.map { $0 as Any } ?? NSNull(),
            "debtsOverdue": debtsOverdue,
            "inboxId": inboxId.map { $0 as Any } ?? NSNull(), "inbox": inbox,
            "progress": ["typed": typed, "total": real],
        ]
        return try json(result)
    }

    // Движение недели: закрытое за 7 дней по корневым категориям — порт today.movement.
    static func movement(_ db: Database) throws -> [String: Any] {
        let nodes = try db.rows("SELECT id, parent_id, title, is_category FROM nodes")
        var byId: [Int: [String: Any]] = [:]
        for n in nodes { byId[intval(n["id"])] = n }
        func rootOf(_ start: [String: Any]) -> String {
            var cur = start
            while let pid = cur["parent_id"] as? Int, let p = byId[pid] {
                if intval(p["is_category"]) != 0 && (p["parent_id"] as? Int) == nil {
                    return p["title"] as? String ?? "прочее"
                }
                cur = p
            }
            return intval(cur["is_category"]) != 0 ? (cur["title"] as? String ?? "прочее") : "прочее"
        }
        let done = try db.rows("""
            SELECT id FROM nodes WHERE is_category = 0
              AND status IN ('done','accepted') AND updated_at >= datetime('now','-7 days')
            """)
        var byCat: [String: Int] = [:]
        for d in done { if let node = byId[intval(d["id"])] { byCat[rootOf(node), default: 0] += 1 } }
        return ["total": done.count,
                "top": byCat.sorted { $0.value > $1.value }.prefix(3).map { [$0.key, $0.value] as [Any] }]
    }

    // Сортировка рутин для дашборда — порт life.sortRoutines.
    static func sortRoutines(_ rows: [[String: Any]]) -> [[String: Any]] {
        let now = Date(); let c = Calendar.current
        let hhmm = String(format: "%02d:%02d", c.component(.hour, from: now), c.component(.minute, from: now))
        let slotOrd = ["утро": 0, "день": 1, "вечер": 2]
        var arr = rows.map { r -> [String: Any] in
            var n = r
            let done = (r["done"] as? Bool) ?? false
            let time = r["time"] as? String
            n["due"] = !done && (time != nil && !(time!.isEmpty)) && (time! <= hhmm)
            return n
        }
        arr.sort { a, b in
            let ad = (a["done"] as? Bool) ?? false, bd = (b["done"] as? Bool) ?? false
            if ad != bd { return !ad }
            let at = a["time"] as? String, bt = b["time"] as? String
            let aHas = at != nil && !(at!.isEmpty), bHas = bt != nil && !(bt!.isEmpty)
            if aHas != bHas { return aHas }
            if aHas, bHas, at! != bt! { return at! < bt! }
            let ao = slotOrd[a["slot"] as? String ?? ""] ?? 9
            let bo = slotOrd[b["slot"] as? String ?? ""] ?? 9
            if ao != bo { return ao < bo }
            return intval(a["ord"]) < intval(b["ord"])
        }
        return arr
    }

    // ===== Числовые / датовые помощники =====
    private static func num(_ v: Any?) -> Double {
        if let d = v as? Double { return d }
        if let i = v as? Int { return Double(i) }
        return 0
    }
    private static func numOpt(_ v: Any?) -> Double? {
        if let d = v as? Double { return d }
        if let i = v as? Int { return Double(i) }
        return nil
    }
    private static func intval(_ v: Any?) -> Int {
        if let i = v as? Int { return i }
        if let d = v as? Double { return Int(d) }
        return 0
    }
    // Разница в днях (UTC midnight, как Date.parse в Node): from → to.
    private static func dayDiff(_ from: String, _ to: String) -> Double? {
        guard let a = ymdUTC.date(from: String(from.prefix(10))),
              let b = ymdUTC.date(from: String(to.prefix(10))) else { return nil }
        return b.timeIntervalSince(a) / 86400
    }
    private static func queryValue(_ query: String?, _ key: String) -> String? {
        guard let query else { return nil }
        for pair in query.split(separator: "&") {
            let kv = pair.split(separator: "=", maxSplits: 1)
            if kv.first.map(String.init) == key {
                let v = kv.count > 1 ? String(kv[1]) : ""
                return v.removingPercentEncoding ?? v
            }
        }
        return nil
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
