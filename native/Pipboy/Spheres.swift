import Foundation

// Сферы жизни на нативном (Swift) — порт логики из app/spheres.js 1:1.
// Сфера = сектор Колеса (wheel_areas) + всё, что к ней привязано тегом area_id.
// Без отдельного хранилища: поверх реальных таблиц. Дефолты секций — в settings.sphere_defaults.
extension Api {

    // ----- схема: area_id на таблицах (тихая миграция) -----
    static func ensureSpheresSchema(_ db: Database) {
        for t in ["nodes", "routines", "metrics", "practices", "obligations", "people", "pages", "events", "debts", "steps"] {
            try? db.run("ALTER TABLE \(t) ADD COLUMN area_id INTEGER REFERENCES wheel_areas(id) ON DELETE SET NULL")
        }
    }

    // ----- дефолты секций -----
    static func sphereDefaults(_ db: Database) -> [String: Int] {
        guard let v = (try? db.rows("SELECT value FROM settings WHERE key = 'sphere_defaults'"))?.first?["value"] as? String,
              let data = v.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return [:] }
        var out: [String: Int] = [:]
        for (k, val) in obj { if let i = val as? Int { out[k] = i } else if let d = val as? Double { out[k] = Int(d) } }
        return out
    }
    @discardableResult
    static func sphereSetDefault(_ db: Database, _ kind: String, _ areaId: Int?) throws -> [String: Int] {
        var d = sphereDefaults(db)
        if let a = areaId { d[kind] = a } else { d.removeValue(forKey: kind) }
        try setSetting(db, "sphere_defaults", String(data: try JSONSerialization.data(withJSONObject: d), encoding: .utf8) ?? "{}")
        return d
    }

    // ----- авто-разложить верхние категории Целей по сферам с совпадающим именем -----
    @discardableResult
    static func autoMapCategories(_ db: Database) throws -> Int {
        let areas = try db.rows("SELECT id, name FROM wheel_areas").map { (id: $0["id"] as? Int ?? -1, n: norm($0["name"] as? String ?? "")) }
        let cats = try db.rows("SELECT id, title FROM nodes WHERE is_category = 1 AND parent_id IS NULL AND area_id IS NULL")
        var mapped = 0
        for c in cats {
            let cn = norm(c["title"] as? String ?? "")
            if !cn.isEmpty, let hit = areas.first(where: { !$0.n.isEmpty && (cn.contains($0.n) || $0.n.contains(cn)) }) {
                try db.run("UPDATE nodes SET area_id = ? WHERE id = ?", [hit.id, c["id"]]); mapped += 1
            }
        }
        return mapped
    }

    // ----- автоматизм: секции в подходящие сферы по смыслу (приоритет по порядку ключей) -----
    static let sphereAutoKeys: [(String, [String])] = [
        ("person", ["социал", "отнош", "друз", "общени", "семь", "партн"]),
        ("metric", ["развит", "обучен", "рост", "прогресс"]),
        ("practice", ["развит", "обучен", "психолог", "осознан", "менталь", "смысл", "перспектив"]),
        ("obligation", ["деньг", "финанс", "инвест", "капитал", "быт", "дом"]),
    ]
    @discardableResult
    static func autoConfigSpheres(_ db: Database, force: Bool = false) throws -> [String: Any] {
        let areas = try db.rows("SELECT id, name FROM wheel_areas ORDER BY ord, id")
            .map { (id: $0["id"] as? Int ?? -1, n: ($0["name"] as? String ?? "").lowercased(), name: $0["name"] as? String ?? "") }
        var d = sphereDefaults(db); var report: [String: Any] = [:]
        for (kind, keys) in sphereAutoKeys {
            if !force, let cur = d[kind] { report[kind] = areas.first(where: { $0.id == cur })?.name ?? "(задано)"; continue }
            var hit: (id: Int, n: String, name: String)? = nil
            for k in keys { if let f = areas.first(where: { $0.n.contains(k) }) { hit = f; break } }
            if let h = hit { d[kind] = h.id; report[kind] = h.name } else { report[kind] = NSNull() }
        }
        try setSetting(db, "sphere_defaults", String(data: try JSONSerialization.data(withJSONObject: d), encoding: .utf8) ?? "{}")
        let mapped = try autoMapCategories(db)
        return ["defaults": report, "categoriesMapped": mapped]
    }

    // ----- резолвер сферы по дереву (ближайший предок с area_id) -----
    private static func makeResolver(_ rows: [[String: Any]]) -> (Int) -> Int? {
        var byId: [Int: (parent: Int?, area: Int?)] = [:]
        for r in rows { if let id = r["id"] as? Int { byId[id] = (r["parent_id"] as? Int, r["area_id"] as? Int) } }
        var memo: [Int: Int?] = [:]
        func resolve(_ id: Int) -> Int? {
            if let m = memo[id] { return m }
            var chain: [Int] = []; var curId: Int? = id; var area: Int? = nil
            while let cid = curId, let node = byId[cid] {
                chain.append(cid)
                if let a = node.area { area = a; break }
                curId = node.parent
            }
            for c in chain { memo[c] = area }
            return area
        }
        return resolve
    }

    private static func sphIso(_ d: Date) -> String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd"; f.locale = Locale(identifier: "en_US_POSIX"); return f.string(from: d)
    }
    // последние 7 дней отметок (старое→новое) для рутины/практики — недельная полоса успеха
    private static func last7Hits(_ db: Database, _ table: String, _ idCol: String, _ id: Int) -> [Int] {
        let cal = Calendar.current
        let days: [String] = stride(from: 6, through: 0, by: -1).map { sphIso(cal.date(byAdding: .day, value: -$0, to: Date()) ?? Date()) }
        let hit = Set((try? db.rows("SELECT date FROM \(table) WHERE \(idCol) = ? AND date >= ?", [id, days.first ?? ""]))?
            .compactMap { ($0["date"] as? String).map { String($0.prefix(10)) } } ?? [])
        return days.map { hit.contains($0) ? 1 : 0 }
    }

    // ===== главный сборщик =====
    static func buildSpheres(_ db: Database) throws -> [[String: Any]] {
        let areas = try db.rows("SELECT * FROM wheel_areas ORDER BY ord, id")
        let resolve = makeResolver(try db.rows("SELECT id, parent_id, area_id FROM nodes"))
        let todayIso = sphIso(Date())
        let since14 = sphIso(Calendar.current.date(byAdding: .day, value: -13, to: Date()) ?? Date())

        let allTasks = try db.rows("SELECT id, title, status, due_date, priority, area_id, note FROM nodes WHERE is_category = 0")
        let allNodes = try db.rows("SELECT id, parent_id, title, is_category, kind, status, due_date, priority, note, answer FROM nodes ORDER BY ord, id")
        var nodeById: [Int: [String: Any]] = [:]
        for n in allNodes { if let id = n["id"] as? Int { nodeById[id] = n } }

        func belongs(_ n: [String: Any], _ aid: Int, _ aname: String) -> Bool {
            if let id = n["id"] as? Int, resolve(id) == aid { return true }
            if let note = n["note"] as? String, note.contains("сектор «\(aname)»") { return true }
            return false
        }

        let allPages = try db.rows("SELECT id, title, parent_id, area_id, node_id FROM pages")
        let resolvePage = makeResolver(allPages)
        let defaults = sphereDefaults(db)
        func whereClause(_ kind: String, _ aid: Int) -> String {
            defaults[kind] == aid ? "(area_id = ? OR area_id IS NULL)" : "area_id = ?"
        }

        // финансовые числа — один раз, в денежной сфере (дефолт obligation)
        let finArea = defaults["obligation"]
        var finNums: [String: Any]? = nil
        if finArea != nil,
           let finData = try? fin(db),
           let finObj = try? JSONSerialization.jsonObject(with: finData) as? [String: Any],
           let summary = finObj["summary"] as? [String: Any] {
            let tx = finObj["tx"] as? [String: Any]
            let fireV = finObj["fire"] as? [String: Any]
            finNums = [
                "capital": summary["portfolioTotal"] ?? NSNull(),
                "expense": tx?["expense"] ?? NSNull(),
                "income": summary["monthlyIncome"] ?? NSNull(),
                "firePct": fireV?["progressPct"] ?? NSNull(),
                "budget": finObj["budget"] ?? NSNull(),
            ]
        }

        var result: [[String: Any]] = []
        for a in areas {
            let aid = a["id"] as? Int ?? -1
            let aname = a["name"] as? String ?? ""
            let sc = try db.rows("SELECT date, score FROM wheel_scores WHERE area_id = ? ORDER BY date DESC LIMIT 8", [aid])

            // задачи: счётчики + дерево с вложенностью
            let areaTasks = allTasks.filter { belongs($0, aid, aname) }
            let tasksTotal = areaTasks.count
            let tasksDone = areaTasks.filter { ($0["status"] as? String) == "done" }.count
            let tasks = sphereTaskTree(aid, aname, allNodes, nodeById, resolve, belongs)

            // рутины
            var routines: [[String: Any]] = []
            for r in try db.rows("SELECT id, name FROM routines WHERE area_id = ? ORDER BY ord, id", [aid]) {
                let rid = r["id"] as? Int ?? -1
                let done = (try? db.rows("SELECT 1 AS x FROM routine_log WHERE routine_id = ? AND date = ?", [rid, todayIso]))?.isEmpty == false
                routines.append(["id": rid, "name": r["name"] ?? "", "streak": (try? routineStreak(db, rid)) ?? 0, "doneToday": done, "wk": last7Hits(db, "routine_log", "routine_id", rid)])
            }

            // метрики (трекинг) — по дефолту секции
            var tracking: [[String: Any]] = []
            for m in try db.rows("SELECT id, name, unit, type FROM metrics WHERE \(whereClause("metric", aid)) ORDER BY ord, id", [aid]) {
                tracking.append(try sphMetricBlock(db, m["id"] as? Int ?? -1, m["name"] as? String ?? "", m["unit"] as? String ?? "", m["type"] as? String ?? ""))
            }

            // практики (психология) — по дефолту секции
            var practices: [[String: Any]] = []
            for p in try db.rows("SELECT * FROM practices WHERE \(whereClause("practice", aid)) ORDER BY ord, id", [aid]) {
                let pid = p["id"] as? Int ?? -1
                practices.append(["id": pid, "name": p["name"] ?? "", "streak": (try? practiceStreak(db, id: pid, days: p["days"] as? String)) ?? 0, "wk": last7Hits(db, "practice_log", "practice_id", pid)])
            }

            // люди (социализация) — по дефолту секции
            var people: [[String: Any]] = []
            for p in try db.rows("SELECT id, name, rhythm_days, last_contact FROM people WHERE \(whereClause("person", aid)) ORDER BY id", [aid]) {
                people.append(["id": p["id"] ?? NSNull(), "name": p["name"] ?? "", "rhythm": p["rhythm_days"] ?? NSNull(), "last": p["last_contact"] ?? NSNull()])
            }

            // инфо — страницы сферы (вложенные наследуют)
            let info = allPages.filter { resolvePage($0["id"] as? Int ?? -1) == aid }.prefix(12).map { ["id": $0["id"] ?? NSNull(), "title": $0["title"] ?? ""] }
            // события
            let events = try db.rows("SELECT id, title, date, time FROM events WHERE area_id = ? ORDER BY date, id LIMIT 12", [aid])

            // финансы — обязательства/долги/шаги по дефолту денежной секции
            let fin = try db.rows("SELECT id, name, amount, currency, period, next_date FROM obligations WHERE \(whereClause("obligation", aid)) ORDER BY id", [aid])
            let debts = try db.rows("SELECT id, name, amount, currency, direction, due_date FROM debts WHERE \(whereClause("obligation", aid)) ORDER BY id", [aid])
            let steps = try db.rows("SELECT id, kind, title, amount, planned_date FROM steps WHERE status = 'planned' AND \(whereClause("obligation", aid)) ORDER BY id", [aid])
            let finance: Any = (aid == finArea ? (finNums ?? NSNull()) : NSNull())

            // живой прогресс
            let rIds = routines.compactMap { $0["id"] as? Int }
            var adherence: Any = NSNull(); var adhValue: Double? = nil
            if !rIds.isEmpty {
                let marks = (try? db.scalarInt("SELECT count(*) FROM routine_log WHERE date >= '\(since14)' AND routine_id IN (\(rIds.map { String($0) }.joined(separator: ",")))")) ?? 0
                let v = min(1.0, Double(marks) / Double(rIds.count * 14)); adhValue = v; adherence = v
            }
            var trends: [[String: Any]] = []
            for m in tracking {
                let s = m["s"] as? [Double] ?? []
                if s.count >= 2 { let dir = (s.last! - s.first!); trends.append(["name": m["name"] ?? "", "dir": dir > 0 ? 1 : (dir < 0 ? -1 : 0)]) }
            }
            var signals: [Double] = []
            if tasksTotal > 0 { signals.append(Double(tasksDone) / Double(tasksTotal)) }
            if let av = adhValue { signals.append(av) }
            let momentum: Any = signals.isEmpty ? NSNull() : Int((signals.reduce(0, +) / Double(signals.count) * 10).rounded())
            let progress: [String: Any] = ["tasksDone": tasksDone, "tasksTotal": tasksTotal, "adherence": adherence, "trends": trends, "momentum": momentum]

            let scores = sc.compactMap { $0["score"] as? Int }
            let scoreVal: Any = sc.first.flatMap { $0["score"] } ?? NSNull()
            let prevVal: Any = sc.count > 1 ? (sc[1]["score"] ?? NSNull()) : NSNull()
            result.append([
                "id": aid, "name": aname,
                "ideal": a["ideal"] ?? "", "current_desc": a["current_desc"] ?? "", "next_desc": a["next_desc"] ?? "", "step": a["step"] ?? "",
                "score": scoreVal, "prev": prevVal,
                "history": Array(scores.reversed()),
                "tasks": tasks, "routines": routines, "tracking": tracking, "practices": practices,
                "people": people, "info": Array(info), "events": events, "fin": fin, "debts": debts, "steps": steps,
                "finance": finance, "progress": progress,
            ])
        }
        return result
    }

    private static func sphMetricBlock(_ db: Database, _ id: Int, _ name: String, _ unit: String, _ type: String) throws -> [String: Any] {
        let rows = Array(try db.rows("SELECT date, value FROM metric_log WHERE metric_id = ? ORDER BY date DESC LIMIT 7", [id]).reversed())
        let s = rows.compactMap { ($0["value"] as? Double) ?? ($0["value"] as? Int).map(Double.init) }
        return ["id": id, "name": name, "unit": unit, "type": type, "v": s.last ?? NSNull(), "s": s]
    }

    // поддерево задач сферы (открытые + категории-предки), как в Целях
    private static func sphereTaskTree(_ aid: Int, _ aname: String, _ allNodes: [[String: Any]], _ nodeById: [Int: [String: Any]],
                                       _ resolve: (Int) -> Int?, _ belongs: ([String: Any], Int, String) -> Bool) -> [[String: Any]] {
        var inc = Set<Int>()
        for n in allNodes {
            if (n["is_category"] as? Int ?? 0) == 1 { continue }
            if (n["status"] as? String) == "done" { continue }
            if !belongs(n, aid, aname) { continue }
            var curId: Int? = n["id"] as? Int
            while let cid = curId, resolve(cid) == aid {
                inc.insert(cid)
                curId = nodeById[cid]?["parent_id"] as? Int
            }
        }
        var kids: [Int: [[String: Any]]] = [:]   // ключ -1 = root
        for n in allNodes {
            guard let id = n["id"] as? Int, inc.contains(id) else { continue }
            let p = (n["parent_id"] as? Int).flatMap { inc.contains($0) ? $0 : nil } ?? -1
            kids[p, default: []].append(n)
        }
        var out: [[String: Any]] = []
        func walk(_ n: [String: Any], _ depth: Int) {
            out.append([
                "id": n["id"] ?? NSNull(), "title": n["title"] ?? "",
                "cat": (n["is_category"] as? Int ?? 0) == 1, "done": (n["status"] as? String) == "done",
                "kind": n["kind"] ?? NSNull(), "status": n["status"] ?? NSNull(),
                "due": n["due_date"] ?? NSNull(), "priority": n["priority"] ?? NSNull(),
                "note": n["note"] ?? "", "answer": n["answer"] ?? NSNull(), "depth": depth,
            ])
            if let id = n["id"] as? Int { for c in kids[id] ?? [] { walk(c, depth + 1) } }
        }
        for n in kids[-1] ?? [] { walk(n, 0) }
        return Array(out.prefix(120))
    }

    // ----- категории / пулы / привязка -----
    static func sphereCategories(_ db: Database) throws -> [[String: Any]] {
        try db.rows("SELECT id, title, parent_id, area_id FROM nodes WHERE is_category = 1 ORDER BY ord, id")
    }
    static func sphereTagPool(_ db: Database) throws -> [String: Any] {
        [
            "areas": try db.rows("SELECT id, name FROM wheel_areas ORDER BY ord, id"),
            "categories": try db.rows("SELECT id, title, parent_id, area_id FROM nodes WHERE is_category = 1 ORDER BY ord, id"),
            "pages": try db.rows("SELECT id, title, parent_id, area_id FROM pages ORDER BY ord, id"),
            "routines": try db.rows("SELECT id, name, area_id FROM routines WHERE planned = 0 ORDER BY ord, id"),
            "events": try db.rows("SELECT id, title AS name, area_id FROM events ORDER BY date, id"),
            "debts": try db.rows("SELECT id, name, area_id FROM debts ORDER BY id"),
            "steps": try db.rows("SELECT id, title AS name, area_id FROM steps WHERE status = 'planned' ORDER BY id"),
        ]
    }
    static func spherePool(_ db: Database) throws -> [String: Any] {
        [
            "areas": try db.rows("SELECT id, name FROM wheel_areas ORDER BY ord, id"),
            "defaults": sphereDefaults(db),
            "routines": try db.rows("SELECT id, name, area_id FROM routines ORDER BY ord, id"),
            "metrics": try db.rows("SELECT id, name, area_id FROM metrics ORDER BY ord, id"),
            "practices": try db.rows("SELECT id, name, area_id FROM practices ORDER BY ord, id"),
            "obligations": try db.rows("SELECT id, name, area_id FROM obligations ORDER BY id"),
            "people": try db.rows("SELECT id, name, area_id FROM people ORDER BY id"),
            "categories": try db.rows("SELECT id, title, area_id FROM nodes WHERE is_category = 1 AND parent_id IS NULL ORDER BY ord, id"),
        ]
    }
    static let sphereTbl: [String: String] = ["routine": "routines", "metric": "metrics", "practice": "practices",
        "obligation": "obligations", "category": "nodes", "person": "people", "page": "pages", "event": "events", "debt": "debts", "step": "steps"]
    static func sphereAssign(_ db: Database, _ kind: String, _ id: Int, _ areaId: Int?) throws {
        guard let t = sphereTbl[kind] else { throw Database.Failure.sql("unknown kind") }
        try db.run("UPDATE \(t) SET area_id = ? WHERE id = ?", [areaId, id])
    }
}
