import Foundation
import WebKit
import CryptoKit
import Network
#if canImport(AppKit)
import AppKit
#endif

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
    // Живые задачи (трогаем только из main, где WebKit зовёт start/stop) — чтобы НЕ
    // отвечать отменённой задаче: на iOS это роняет WebContent-процесс.
    private var active = Set<ObjectIdentifier>()

    private func database() throws -> Database {
        if let db { return db }
        // ключ кладёт AuthGate под пальцем; ждём недолго, если ещё не готов
        var key = KeyHolder.shared.key, tries = 0
        while key == nil && tries < 50 { usleep(100_000); key = KeyHolder.shared.key; tries += 1 }
        guard let k = key else { throw Database.Failure.open(0) }
        let made = try Database(key: k)
        _ = try? made.run("DELETE FROM trash WHERE created_at < datetime('now','-30 days')")  // авто-очистка корзины
        _ = try? made.run("ALTER TABLE nodes ADD COLUMN due_time TEXT")  // миграция: время у задач (тихо, если уже есть)
        _ = try? made.run("ALTER TABLE nodes ADD COLUMN answer TEXT")    // формулировка решения — buildSpheres селектит явно, без неё сферы падали
        _ = try? made.run("ALTER TABLE nodes ADD COLUMN \"repeat\" TEXT") // повтор задачи (weekly|monthly|yearly)
        _ = try? made.run("ALTER TABLE obligations ADD COLUMN due_time TEXT")  // миграция: время у обязательств (как due_time задач)
        _ = try? made.run("ALTER TABLE portfolio_items ADD COLUMN region TEXT")  // регион инвестиции (SK/UA/AU/EU/WEB)
        _ = try? made.run("ALTER TABLE target_items ADD COLUMN region TEXT")
        _ = try? made.run("ALTER TABLE routines ADD COLUMN days TEXT NOT NULL DEFAULT ''")  // дни недели рутины (пусто = каждый день)
        _ = try? made.run("ALTER TABLE passive_income ADD COLUMN principal REAL NOT NULL DEFAULT 0")    // тело инвестиции/депозита
        _ = try? made.run("ALTER TABLE passive_income ADD COLUMN rate REAL NOT NULL DEFAULT 0")         // % доходности
        _ = try? made.run("ALTER TABLE passive_income ADD COLUMN rate_period TEXT NOT NULL DEFAULT 'yearly'")  // период ставки: yearly|monthly
        _ = try? made.run("ALTER TABLE passive_income ADD COLUMN asset_type TEXT NOT NULL DEFAULT ''")  // тип актива
        _ = try? made.run("CREATE TABLE IF NOT EXISTS attachments(id INTEGER PRIMARY KEY, page_id INTEGER, name TEXT NOT NULL DEFAULT '', mime TEXT NOT NULL DEFAULT 'application/octet-stream', data TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')))")  // вложения Инфо (картинки/PDF)
        _ = try? made.run("ALTER TABLE practices ADD COLUMN category TEXT NOT NULL DEFAULT ''")  // категория практики
        _ = try? made.run("ALTER TABLE metrics ADD COLUMN target REAL")                          // KPI метрики — без неё сферы падали
        _ = try? made.run("ALTER TABLE metrics ADD COLUMN polarity TEXT NOT NULL DEFAULT 'plus'") // полярность метрики
        _ = try? made.run("CREATE TABLE IF NOT EXISTS budget_items(id INTEGER PRIMARY KEY, direction TEXT NOT NULL DEFAULT 'expense', name TEXT NOT NULL DEFAULT '', amount REAL NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT '€', ord INTEGER NOT NULL DEFAULT 0, month TEXT)")  // дефолтные расходы/доходы — миграция существующих баз (ensureSchema идёт только при сиде)
        _ = try? made.run("ALTER TABLE budget_items ADD COLUMN month TEXT")   // доход — помесячно (YYYY-MM); расход — пусто (фикс/мес)
        // целевой портфель — отдельное дерево. Если таблица осталась старой (плоской, без parent_id) — пересоздаём,
        // иначе portfolioTree(ORDER BY parent_id) падает → /api/fin 500 → белый экран Финансов.
        if !(((try? made.rows("PRAGMA table_info(target_items)")) ?? []).contains { ($0["name"] as? String) == "parent_id" }) {
            _ = try? made.run("DROP TABLE IF EXISTS target_items")
            _ = try? made.run("UPDATE settings SET value = '' WHERE key = 'target_seed_v1'")   // сброс → перезаполним копией факта
        }
        _ = try? made.run("CREATE TABLE IF NOT EXISTS target_items(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES target_items(id) ON DELETE CASCADE, ord INTEGER NOT NULL DEFAULT 0, name TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'asset', value REAL, buy_value REAL, target_value REAL, currency TEXT NOT NULL DEFAULT '€', asset_type TEXT, qty REAL, rate_symbol TEXT, note TEXT)")
        _ = try? made.run("CREATE TABLE IF NOT EXISTS target_moves(id INTEGER PRIMARY KEY, from_id INTEGER REFERENCES target_items(id) ON DELETE CASCADE, to_id INTEGER REFERENCES target_items(id) ON DELETE CASCADE, amount REAL NOT NULL DEFAULT 0)")  // ручные связки ребаланса
        // одноразовый сброс целевого по запросу: очистить и пересоздать свежей копией факта
        // (v4 — пересоздаём целевой после фикса порядка: initTargetFromFact теперь проставляет parent 2-м проходом,
        //  иначе часть позиций выпадала из категорий, если id раздела < id блока)
        if ((try? made.rows("SELECT value FROM settings WHERE key = 'target_reset_v4'"))?.first?["value"]) as? String != "1" {
            _ = try? made.run("DELETE FROM target_moves")
            _ = try? made.run("DELETE FROM target_items")
            _ = try? made.run("UPDATE settings SET value = '' WHERE key = 'target_seed_v1'")   // сброс флага → initTargetFromFact заполнит заново
            _ = try? Api.setSetting(made, "target_reset_v4", "1")
        }
        Api.dedupeTreeItems(made, "portfolio_items", nil)   // сначала чистим ФАКТ от дублей (синхрон с разными id)
        Api.initTargetFromFact(made)   // первый раз (и после сброса) — копируем структуру фактического портфеля в целевой
        Api.dedupeTreeItems(made, "target_items", "target_moves")   // и целевой
        // разовая чистка целевого от ТОЧНЫХ дублей, раскиданных по разным категориям (последствие прошлых синхронов)
        if ((try? made.rows("SELECT value FROM settings WHERE key = 'target_exact_dedup_v1'"))?.first?["value"]) as? String != "1" {
            Api.dedupeTargetExact(made)
            _ = try? Api.setSetting(made, "target_exact_dedup_v1", "1")
        }
        _ = try? made.run("UPDATE target_items SET rate_symbol = NULL, qty = NULL WHERE rate_symbol IS NOT NULL")   // целевой — плановые суммы, без автоцены (иначе не отредактировать)
        _ = try? made.run("UPDATE target_items SET target_value = value WHERE target_value IS NULL AND value IS NOT NULL")   // план по умолчанию = текущая стоимость (пока не задан вручную)
        Api.ensureSpheresSchema(made)   // таблицы сфер (area_milestones/area_questions) — до sync-схемы, чтобы им добавились updated_at/триггеры
        Api.ensureSyncSchema(made)   // updated_at + триггеры + tombstones — отслеживание правок для синхрона
        Api.ensureThoughtTesting(made)   // техника «Тестирование мыслей» (КПТ) — один раз
        Api.ensureThoughtDiary(made)   // техника «Дневник мыслей» (журнал таблицей) — один раз
        Api.ensureExperienceDiary(made)   // техника «Дневник Опыта» — один раз
        Api.ensureWinsDiary(made)   // техника «Дневник Побед» — один раз
        Api.ensureTuningDiary(made)   // техника «Дневник настройки» (+ заполнение образа себя) — один раз
        Api.ensurePracticeCategories(made)   // категории практик по умолчанию — один раз
        Api.ensurePositiveIntent(made)   // техника «Позитивное намерение» (+ обновление формулировки шагов)
        Api.seedThoughtDiaryEntries(made)   // разобранные случаи в журнал «Дневника мыслей» — один раз
        Api.dedupePractices(made)   // свести дубли практик по имени (расходятся после синхрона Mac↔iPhone с разными id)
        Api.seedBudgetItems(made)   // дефолтные расходы/доходы: первичное заполнение из транзакций месяца-базы (2026-06)
        if (try? made.rows("SELECT value FROM settings WHERE key = 'sphere_defaults'"))?.first == nil {
            try? Api.autoConfigSpheres(made)   // первый запуск: связи секций раскладываются сами
        }
        db = made
        return made
    }

    func webView(_ webView: WKWebView, start task: WKURLSchemeTask) {
        let id = ObjectIdentifier(task)
        active.insert(id)   // start вызывается WebKit на main
        let url = task.request.url ?? URL(string: "pipboy://app/")!
        let method = task.request.httpMethod ?? "GET"
        let bodyHeader = task.request.value(forHTTPHeaderField: "X-Pipboy-Body")
        queue.async {
            var result: (Data, String, Int)
            do { result = try self.respond(to: url, method: method, bodyHeader: bodyHeader) }
            catch {
                // корректно кодируем ошибку в JSON: текст ошибки мог содержать кавычки/переводы строк
                // и ломать тело ответа — тогда фронт ловил парс-ошибку и показывал общий фолбэк
                let body = (try? JSONSerialization.data(withJSONObject: ["error": String(describing: error)]))
                    ?? Data("{\"error\":\"internal\"}".utf8)
                result = (body, "application/json", 500)
            }
            // отвечаем на main и только если задача ещё жива (иначе краш web-процесса на iOS)
            DispatchQueue.main.async {
                guard self.active.remove(id) != nil else { return }
                let resp = HTTPURLResponse(url: url, statusCode: result.2, httpVersion: "HTTP/1.1",
                    headerFields: ["Content-Type": result.1, "Cache-Control": "no-store"])!
                task.didReceive(resp)
                task.didReceive(result.0)
                task.didFinish()
            }
        }
    }

    func webView(_ webView: WKWebView, stop task: WKURLSchemeTask) {
        active.remove(ObjectIdentifier(task))   // отменена — больше не трогаем
    }

    private func respond(to url: URL, method: String, bodyHeader: String?) throws -> (Data, String, Int) {
        let path = url.path.isEmpty ? "/" : url.path
        if path.hasPrefix("/api/") {
            // вложения Инфо отдаём бинарём с настоящим MIME (картинки/PDF), а не JSON
            if method == "GET", let (data, mime) = try Api.attachmentBinary(try database(), path: path) {
                return (data, mime, 200)
            }
            var body: [String: Any]? = nil
            if let raw = bodyHeader?.removingPercentEncoding, let d = raw.data(using: .utf8) {
                body = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any]
            }
            let (data, status) = try Api.handle(method: method, path: path, query: url.query, body: body, db: try database())
            return (data, "application/json", status)
        }
        return try staticFile(path)
    }

    // Корень фронта: Mac — клон на диске (обновляется git pull); iOS — фронт,
    // прилетевший по Wi-Fi (свежее бандла), иначе вшитый в бандл.
    static var webRoot: URL {
        #if os(macOS)
        // dev: живой клон на диске (правки видны сразу, обновляется git pull)
        let dev = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Downloads/cladue/app/public", isDirectory: true)
        if FileManager.default.fileExists(atPath: dev.appendingPathComponent("index.html").path) { return dev }
        // упаковано: фронт из бандла .app (public/ как folder reference) — .app самодостаточен
        let res = Bundle.main.resourceURL ?? Bundle.main.bundleURL
        let withPublic = res.appendingPathComponent("public", isDirectory: true)
        if FileManager.default.fileExists(atPath: withPublic.appendingPathComponent("index.html").path) { return withPublic }
        return res
        #else
        if let o = webOverrideDir { return o }   // фронт, полученный по синхрону
        // в бандле фронт может лежать как папка public/ (folder reference) или плоско (group)
        let res = Bundle.main.resourceURL ?? Bundle.main.bundleURL
        let withPublic = res.appendingPathComponent("public", isDirectory: true)
        if FileManager.default.fileExists(atPath: withPublic.appendingPathComponent("index.html").path) { return withPublic }
        return res
        #endif
    }

    // Куда синхрон кладёт обновлённый фронт на iPhone (рядом с базой, вне бандла).
    static var webDir: URL { (try? Database.fileURL())?.deletingLastPathComponent()
        .appendingPathComponent("web", isDirectory: true)
        ?? URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("web") }
    static var webOverrideDir: URL? {
        let d = webDir
        return FileManager.default.fileExists(atPath: d.appendingPathComponent("index.html").path) ? d : nil
    }

    // Тот же фронт из app/public (host в pipboy://app/... игнорируем).
    private func staticFile(_ path: String) throws -> (Data, String, Int) {
        var rel = (path == "/") ? "index.html" : path
        if rel.hasPrefix("/") { rel.removeFirst() }
        let base = Self.webRoot.standardizedFileURL
        let file = base.appendingPathComponent(rel).standardizedFileURL
        // защита от обхода каталога (../): файл обязан оставаться внутри public
        guard file.path == base.path || file.path.hasPrefix(base.path + "/") else { throw Database.Failure.open(404) }
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
        if path == "/api/rest" { return (try json(try db.rows("SELECT id, text, scope FROM rest_ideas ORDER BY ord, id")), 200) }
        // ----- Сферы -----
        if path == "/api/spheres" { return (try json(try buildSpheres(db)), 200) }
        if path == "/api/spheres/pool" { return (try json(try spherePool(db)), 200) }
        if path == "/api/reports/spheres" { return (try json(try reportSpheres(db, queryValue(query, "period") ?? "month")), 200) }
        if path == "/api/reports/dynamics" { return (try json(try reportDynamics(db, Int(queryValue(query, "months") ?? "6") ?? 6)), 200) }
        if let m = match(path, "^/api/track/metrics/([0-9]+)/logs$") {   // все записи метрики (дата+значение) — просмотр/чистка
            return (try json(try db.rows("SELECT date, value FROM metric_log WHERE metric_id = ? ORDER BY date DESC", [Int(m[1]) ?? -1])), 200)
        }
        if path == "/api/spheres/tagpool" { return (try json(try sphereTagPool(db)), 200) }
        if path == "/api/spheres/categories" { return (try json(try sphereCategories(db)), 200) }
        // параметрические GET (карточка-инспектор узла)
        if let m = match(path, "^/api/suggest/([0-9]+)$") {
            return (try suggest(db, id: Int(m[1]) ?? -1), 200)
        }
        if let m = match(path, "^/api/nodes/([0-9]+)/log$") {
            return (try json(try db.rows(
                "SELECT * FROM node_log WHERE node_id = ? ORDER BY date DESC, id DESC LIMIT 10", [Int(m[1]) ?? -1])), 200)
        }
        if let m = match(path, "^/api/pages/([0-9]+)/revisions$") {
            return (try json(try db.rows(
                "SELECT id, saved_at, length(content) AS len, substr(content,1,90) AS preview FROM page_revisions WHERE page_id = ? ORDER BY id DESC", [Int(m[1]) ?? -1])), 200)
        }
        if let m = match(path, "^/api/pages/([0-9]+)/backlinks$") {
            return (try json(try backlinks(db, id: Int(m[1]) ?? -1)), 200)
        }
        if let m = match(path, "^/api/psy/practices/([0-9]+)/logs$") {
            return (try json(try db.rows("SELECT * FROM practice_log WHERE practice_id = ? ORDER BY date DESC, id DESC LIMIT 200", [Int(m[1]) ?? -1])
                .map { r -> [String: Any] in
                    var x = r
                    if let s = r["answers"] as? String, let a = try? JSONSerialization.jsonObject(with: Data(s.utf8)) { x["answers"] = a }
                    return x
                }), 200)
        }
        if let m = match(path, "^/api/pages/([0-9]+)$") {
            guard var pg = try getPage(db, Int(m[1]) ?? -1) else { return (try json(["error": "not found"]), 404) }
            pg.removeValue(forKey: "enc")   // шифротекст наружу не отдаём
            return (try json(pg), 200)
        }
        switch path {
        case "/api/info":
            return (try json(["lan": NSNull(), "demoWiped": true, "version": "native"]), 200)
        case "/api/lock":
            return (try json(["enabled": try db.lockEnabled(), "localUnlock": true]), 200)
        case "/api/tree":
            return (try tree(db), 200)
        case "/api/pages":
            return (try json(try db.rows(
                "SELECT id, parent_id, ord, title, node_id, locked, updated_at, area_id FROM pages ORDER BY parent_id NULLS FIRST, ord, id")), 200)
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
        case "/api/wiki":
            return (try json(try resolveWiki(db, name: queryValue(query, "name") ?? "")), 200)
        case "/api/pages/search":
            return (try json(try searchPages(db, q: queryValue(query, "q") ?? "")), 200)
        case "/api/search":
            return (try json(try searchNodes(db, q: queryValue(query, "q") ?? "")), 200)
        case "/api/roulette":
            return (try json(["idea": try rollIdea(db)]), 200)
        case "/api/audit":
            return (try json(try audit(db)), 200)
        case "/api/categories":
            return (try json(try listCategories(db)), 200)
        default:
            throw Unsupported(path: path)
        }
    }

    static func searchNodes(_ db: Database, q: String) throws -> [[String: Any]] {
        let toks = tokens(q)
        if toks.isEmpty { return [] }
        let m = toks.map { "\"\($0.replacingOccurrences(of: "\"", with: ""))\"*" }.joined(separator: " ")
        return try db.rows("SELECT n.* FROM node_fts JOIN nodes n ON n.id = node_fts.rowid WHERE node_fts MATCH ? ORDER BY bm25(node_fts) LIMIT 20", [m])
    }
    static func rollIdea(_ db: Database) throws -> Any {
        // живая хотелка: тип «идея» ИЛИ внутри категории «Банк впечатлений» (любого типа)
        var sql = """
            SELECT id, title, created_at FROM nodes WHERE is_category = 0
              AND (status IS NULL OR status NOT IN ('done','accepted')) AND due_date IS NULL AND (kind = 'idea'
            """
        var params: [Any?] = []
        if let bank = try db.rows("SELECT id FROM nodes WHERE is_category = 1 AND title LIKE '%впечатлен%'").first {
            sql += " OR id IN (WITH RECURSIVE r(x) AS (SELECT id FROM nodes WHERE parent_id = ? UNION SELECT n.id FROM nodes n JOIN r ON n.parent_id = r.x) SELECT x FROM r)"
            params.append(intval(bank["id"]))
        }
        sql += ") ORDER BY RANDOM() LIMIT 1"
        guard let n = try db.rows(sql, params).first else { return NSNull() }
        var path: [String] = []
        var p = numOpt(n["parent_id"]).map { Int($0) }
        while let pid = p, let r = try getNode(db, pid) {
            path.insert(r["title"] as? String ?? "", at: 0)
            p = numOpt(r["parent_id"]).map { Int($0) }
        }
        var days = 0
        if let ca = n["created_at"] as? String, let d = sqliteDate(ca) { days = max(0, Int(Date().timeIntervalSince(d) / 86400)) }
        return ["id": n["id"] ?? NSNull(), "title": n["title"] ?? NSNull(), "path": path.joined(separator: " › "), "days": days]
    }
    static func audit(_ db: Database) throws -> [[String: Any]] {
        var out: [[String: Any]] = []
        func add(_ s: String, _ st: String, _ item: String, _ hint: String = "") { out.append(["section": s, "status": st, "item": item, "hint": hint]) }
        func c(_ sql: String) -> Int { (((try? db.rows(sql))?.first?["c"]) as? Int) ?? 0 }
        let real = c("SELECT count(*) AS c FROM nodes WHERE is_category = 0")
        let untyped = c("SELECT count(*) AS c FROM nodes WHERE is_category = 0 AND kind IS NULL")
        if real == 0 { add("Цели", "warn", "записей нет вообще", "вставь свои списки в поле импорта") }
        else if untyped > real / 2 { add("Цели", "warn", "разобрано мало: без типа \(untyped) из \(real)", "пройдись по инбоксу") }
        else { add("Цели", "ok", "записей \(real), без типа \(untyped)") }
        let p01 = c("SELECT count(*) AS c FROM nodes WHERE kind = 'task' AND priority IN ('P0','P1') AND due_date IS NULL AND status IS NOT 'done'")
        if p01 > 0 { add("Цели", "warn", "важных задач без срока: \(p01)", "P0/P1 без даты не попадут в неделю") }
        let accs = c("SELECT count(*) AS c FROM accounts")
        if accs == 0 { add("Финансы", "warn", "счета не заведены") }
        else {
            let stale = c("SELECT count(*) AS c FROM accounts WHERE julianday('now','localtime') - julianday(balance_updated_at) > 14")
            add("Финансы", stale > 0 ? "warn" : "ok", stale > 0 ? "балансы протухли (>14 дн): \(stale) из \(accs)" : "счета: \(accs), балансы свежие")
        }
        let pages = c("SELECT count(*) AS c FROM pages")
        add("Инфо", pages > 0 ? "ok" : "warn", pages > 0 ? "страниц: \(pages)" : "страниц нет")
        let checkinToday = c("SELECT count(*) AS c FROM checkins WHERE date = date('now','localtime')")
        add("Трекинг", checkinToday > 0 ? "ok" : "warn", checkinToday > 0 ? "чек-ин сегодня есть" : "нет чек-ина сегодня", "10 секунд в дашборде")
        return out
    }

    static func backlinks(_ db: Database, id: Int) throws -> [[String: Any]] {
        guard let p = try getPage(db, id) else { return [] }
        let t = (p["title"] as? String ?? "").lowercased()
        let md = "[[" + t + "]]", html = "data-wiki=\"" + t + "\""   // markdown-вики и HTML-вики
        return try db.rows("SELECT id, title, content FROM pages WHERE id != ?", [id])
            .filter { let c = ($0["content"] as? String ?? "").lowercased(); return c.contains(md) || c.contains(html) }
            .map { ["id": $0["id"] ?? NSNull(), "title": $0["title"] ?? NSNull()] }
    }
    static func resolveWiki(_ db: Database, name: String) throws -> [String: Any] {
        let target = norm(name)
        if let page = try db.rows("SELECT id, title FROM pages").first(where: { norm($0["title"] as? String ?? "") == target }) {
            return ["type": "page", "id": page["id"] ?? NSNull()]
        }
        if let node = try db.rows("SELECT id, title FROM nodes WHERE is_category = 0").first(where: { norm($0["title"] as? String ?? "") == target }) {
            return ["type": "node", "id": node["id"] ?? NSNull()]
        }
        return [:]
    }
    static func searchPages(_ db: Database, q: String) throws -> [[String: Any]] {
        let toks = tokens(q)
        if toks.isEmpty { return [] }
        let m = toks.map { "\"\($0.replacingOccurrences(of: "\"", with: ""))\"*" }.joined(separator: " ")
        return try db.rows("SELECT p.id, p.title FROM page_fts JOIN pages p ON p.id = page_fts.rowid WHERE page_fts MATCH ? ORDER BY bm25(page_fts) LIMIT 10", [m])
    }
    private static let STOP: Set<String> = ["и", "в", "на", "с", "по", "за", "до", "от", "для", "не", "что", "как", "это",
        "или", "у", "мы", "я", "к", "о", "же", "бы", "из", "со", "свой", "наш", "еще", "ещё", "при", "то", "ли", "если",
        "есть", "будет", "надо", "чтоб", "чтобы", "когда", "раз", "the", "to", "of", "and", "a", "in", "is"]
    private static func tokens(_ s: String) -> [String] {
        var seen = Set<String>(); var out: [String] = []
        for t in norm(s).split(whereSeparator: { !($0.isLetter || $0.isNumber) }).map(String.init)
            where t.count >= 2 && !STOP.contains(t) {
            if seen.insert(t).inserted { out.append(t) }
        }
        return out
    }

    // ===== ЗАПИСЬ (Этап 2). Пока — узлы целей; остальные разделы добавляем срезами. =====
    static func write(method: String, path: String, body: [String: Any], db: Database) throws -> (Data, Int) {
        // ----- Сферы: привязка/дефолты/автонастройка -----
        if method == "POST", path == "/api/spheres/assign" {
            guard let kind = body["kind"] as? String, let id = numOpt(body["id"]).map({ Int($0) }) else { return (try json(["error": "kind/id required"]), 400) }
            let area = numOpt(body["areaId"]).map { Int($0) }
            do { try sphereAssign(db, kind, id, area); return (try json(["ok": true]), 200) }
            catch { return (try json(["error": "\(error)"]), 400) }
        }
        if method == "POST", path == "/api/spheres/default" {
            guard let kind = body["kind"] as? String else { return (try json(["error": "kind required"]), 400) }
            let area = numOpt(body["areaId"]).map { Int($0) }
            return (try json(try sphereSetDefault(db, kind, area)), 200)
        }
        // ----- Отдых/восстановление -----
        if method == "POST", path == "/api/rest" {
            let text = (body["text"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            guard !text.isEmpty else { return (try json(["error": "text required"]), 400) }
            let scope = ["weekday", "weekend", "global"].contains(body["scope"] as? String ?? "") ? (body["scope"] as! String) : "weekday"
            try db.run("INSERT INTO rest_ideas(text, scope, ord) VALUES(?,?, (SELECT COALESCE(MAX(ord),0)+1 FROM rest_ideas))", [text, scope])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/rest/([0-9]+)$"), method == "DELETE" {
            try db.run("DELETE FROM rest_ideas WHERE id = ?", [Int(m[1]) ?? -1]); return (ok(), 200)
        }
        if method == "POST", path == "/api/spheres/automap" { return (try json(["mapped": try autoMapCategories(db)]), 200) }
        if method == "POST", path == "/api/spheres/auto" { return (try json(try autoConfigSpheres(db, force: true)), 200) }
        // ----- Вехи «пути к 10» -----
        if method == "POST", path == "/api/spheres/milestone" {
            guard let area = numOpt(body["areaId"]).map({ Int($0) }) else { return (try json(["error": "areaId required"]), 400) }
            let level = max(1, min(10, Int(num(body["level"]).rounded())))
            let title = (body["title"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            try db.run("INSERT INTO area_milestones(area_id, level, title, ord) VALUES(?,?,?, (SELECT COALESCE(MAX(ord),0)+1 FROM area_milestones))", [area, level, title])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/spheres/milestone/([0-9]+)$") {
            let id = Int(m[1]) ?? -1
            if method == "PATCH" {
                if let t = body["title"] as? String { try db.run("UPDATE area_milestones SET title = ? WHERE id = ?", [t, id]) }
                if body["level"] != nil { try db.run("UPDATE area_milestones SET level = ? WHERE id = ?", [max(1, min(10, Int(num(body["level"]).rounded()))), id]) }
                if body["progress"] != nil {
                    let p = max(0, min(10, Int(num(body["progress"]).rounded())))
                    try db.run("UPDATE area_milestones SET progress = ? WHERE id = ?", [p, id])   // прогресс вехи 0→10
                    // дата закрытия (первая фиксируется, при откате <10 сбрасывается) — для счётчиков «закрытые вехи за период»
                    if p >= 10 { try db.run("UPDATE area_milestones SET completed_at = COALESCE(completed_at, ?) WHERE id = ?", [localToday(), id]) }
                    else { try db.run("UPDATE area_milestones SET completed_at = NULL WHERE id = ?", [id]) }
                }
                if body["pinned"] != nil { try db.run("UPDATE area_milestones SET pinned = ? WHERE id = ?", [intval(body["pinned"]) != 0 ? 1 : 0, id]) }   // закрепить → видна на главной
                return (ok(), 200)
            }
            if method == "DELETE" { try db.run("DELETE FROM area_milestones WHERE id = ?", [id]); return (ok(), 200) }
        }
        // ----- FAQ сферы: вопрос→ответ (+ опц. связь с задачей/метрикой) -----
        if method == "POST", path == "/api/spheres/question" {
            guard let area = numOpt(body["areaId"]).map({ Int($0) }) else { return (try json(["error": "areaId required"]), 400) }
            let q = (body["question"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            let a = body["answer"] as? String ?? ""
            let id = try db.run("INSERT INTO area_questions(area_id, question, answer, ord) VALUES(?,?,?, (SELECT COALESCE(MAX(ord),0)+1 FROM area_questions))", [area, q, a])
            return (try json(["id": id]), 201)
        }
        if let m = match(path, "^/api/spheres/question/([0-9]+)$") {
            let id = Int(m[1]) ?? -1
            if method == "PATCH" {
                if let q = body["question"] as? String { try db.run("UPDATE area_questions SET question = ? WHERE id = ?", [q, id]) }
                if let a = body["answer"] as? String { try db.run("UPDATE area_questions SET answer = ? WHERE id = ?", [a, id]) }
                if body["node_id"] != nil { try db.run("UPDATE area_questions SET node_id = ? WHERE id = ?", [numOpt(body["node_id"]).map { Int($0) }, id]) }
                if body["metric_id"] != nil { try db.run("UPDATE area_questions SET metric_id = ? WHERE id = ?", [numOpt(body["metric_id"]).map { Int($0) }, id]) }
                return (ok(), 200)
            }
            if method == "DELETE" { try db.run("DELETE FROM area_questions WHERE id = ?", [id]); return (ok(), 200) }
        }
        if let m = match(path, "^/api/spheres/question/([0-9]+)/reorder$"), method == "POST" {
            guard let ref = numOpt(body["ref"]).map({ Int($0) }) else { return (try json(["error": "ref required"]), 400) }
            do { try reorderSimple(db, "area_questions", id: Int(m[1]) ?? -1, refId: ref, pos: (body["where"] as? String) == "before" ? "before" : "after"); return (ok(), 200) }
            catch { return (errJson(error), 400) }
        }
        if method == "POST", path == "/api/nodes" {
            guard let title = (body["title"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !title.isEmpty else { return (try json(["error": "title required"]), 400) }
            let parent = numOpt(body["parent_id"]).map { Int($0) }
            let isCat = intval(body["is_category"]) != 0
            let id = try insertNode(db, parentId: parent, title: title, note: "", isCategory: isCat ? 1 : 0)
            if !isCat {   // авто-тип по тексту (как addChildAuto в Node)
                var patch: [String: Any] = [:]
                if let k = suggestKind(title) { patch["kind"] = k }
                if let d = suggestDate(title) { patch["due_date"] = d }
                if !patch.isEmpty { _ = try updateNode(db, id: id, fields: patch) }
            }
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
            do { return (try json(try reorderNode(db, id: Int(m[1]) ?? -1, refId: ref, pos: w) ?? [:]), 200) }
            catch { return (try json(["error": "\(error)"]), 400) }
        }
        if let m = match(path, "^/api/nodes/([0-9]+)/move$"), method == "POST" {
            let parent = numOpt(body["parent_id"]).map { Int($0) }
            return (try json(try moveNode(db, id: Int(m[1]) ?? -1, newParent: parent) ?? [:]), 200)
        }
        if let m = match(path, "^/api/nodes/([0-9]+)/log$"), method == "POST" {
            guard let note = (body["note"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !note.isEmpty else { return (try json(["error": "note required"]), 400) }
            try addNodeLog(db, nodeId: Int(m[1]) ?? -1, note: note)
            return (try json(["ok": true]), 201)
        }
        if let m = match(path, "^/api/nodelog/([0-9]+)$"), method == "DELETE" {
            try db.run("DELETE FROM node_log WHERE id = ?", [Int(m[1]) ?? -1]); return (ok(), 200)
        }

        // ----- Рутины -----
        if method == "POST", path == "/api/routines" {
            guard let name = name(body) else { return (nameErr(), 400) }
            let ord = nextOrd(db, "SELECT COALESCE(MAX(ord),0)+1 AS o FROM routines")
            try db.run("INSERT INTO routines(name, slot, time, ord, note, planned, days) VALUES(?,?,?,?,?,?,?)",
                [name, body["slot"] as? String ?? "утро", body["time"] ?? NSNull(), ord, body["note"] as? String ?? "",
                 (body["planned"] as? Bool == true || intval(body["planned"]) != 0) ? 1 : 0, body["days"] as? String ?? ""])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/routines/([0-9]+)/check$"), method == "POST" {
            return (try json(["done": try toggleRoutineToday(db, Int(m[1]) ?? -1)]), 200)
        }
        if let m = match(path, "^/api/routines/([0-9]+)$") {
            let id = Int(m[1]) ?? -1
            if method == "PATCH" { try patchCols(db, "routines", id, ["name", "slot", "time", "note", "planned", "days", "archived"], body); return (ok(), 200) }
            if method == "DELETE" { try db.run("DELETE FROM routines WHERE id = ?", [id]); return (ok(), 200) }
        }

        // ----- Люди -----
        if method == "POST", path == "/api/people" {
            guard let name = name(body) else { return (nameErr(), 400) }
            try db.run("INSERT INTO people(name, birthday, rhythm_days, last_contact, note) VALUES(?,?,?,?,?)",
                [name, body["birthday"] ?? NSNull(), body["rhythm_days"] ?? NSNull(), body["last_contact"] ?? NSNull(), body["note"] as? String ?? ""])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/people/([0-9]+)/contacted$"), method == "POST" {
            let id = Int(m[1]) ?? -1
            try db.run("UPDATE people SET last_contact = ? WHERE id = ?", [localToday(), id])
            if let note = (body["note"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), !note.isEmpty {
                try db.run("INSERT INTO contact_log(person_id, note) VALUES(?,?)", [id, note])
            }
            return (ok(), 200)
        }
        if let m = match(path, "^/api/people/([0-9]+)$") {
            let id = Int(m[1]) ?? -1
            if method == "PATCH" { try patchCols(db, "people", id, ["name", "birthday", "rhythm_days", "last_contact", "tags", "note"], body); return (ok(), 200) }
            if method == "DELETE" { try db.run("DELETE FROM people WHERE id = ?", [id]); return (ok(), 200) }
        }

        // ----- Инфо: страницы -----
        if method == "POST", path == "/api/pages" {
            guard let title = name(body, "title") else { return (try json(["error": "title required"]), 400) }
            return (try json(try addPage(db, title: title, body: body)), 201)
        }
        if let m = match(path, "^/api/pages/([0-9]+)/attachments$"), method == "POST" {
            let pid = Int(m[1]) ?? -1
            let nid = try db.run("INSERT INTO attachments(page_id, name, mime, data) VALUES(?,?,?,?)",
                [pid, body["name"] as? String ?? "", body["mime"] as? String ?? "application/octet-stream", body["data"] as? String ?? ""])
            return (try json(["id": nid, "name": body["name"] ?? "", "mime": body["mime"] ?? "", "url": "/api/attachments/\(nid)"]), 201)
        }
        if let m = match(path, "^/api/pages/([0-9]+)/reorder$"), method == "POST" {
            guard let ref = numOpt(body["ref_id"]).map({ Int($0) }) else { return (try json(["error": "ref_id"]), 400) }
            do { try reorderPage(db, id: Int(m[1]) ?? -1, refId: ref, pos: (body["where"] as? String) == "before" ? "before" : "after"); return (ok(), 200) }
            catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/pages/([0-9]+)/move$"), method == "POST" {
            do { return (try json(try movePage(db, id: Int(m[1]) ?? -1, parent: numOpt(body["parent_id"]).map { Int($0) }) ?? [:]), 200) }
            catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/pages/([0-9]+)$") {
            let id = Int(m[1]) ?? -1
            if method == "PATCH" { do { return (try json(try patchPage(db, id: id, body: body) ?? [:]), 200) } catch { return (errJson(error), 400) } }
            if method == "DELETE" { return (try json(try delPage(db, id: id)), 200) }
        }

        // ----- Психология -----
        if method == "POST", path == "/api/psy/practices" {
            guard let name = name(body) else { return (nameErr(), 400) }
            let ord = nextOrd(db, "SELECT COALESCE(MAX(ord),0)+1 AS o FROM practices")
            let steps = String(data: (try? json(body["steps"] ?? [])) ?? Data("[]".utf8), encoding: .utf8) ?? "[]"
            try db.run("INSERT INTO practices(name, kind, days, time, steps, note, ord, continuous) VALUES(?,?,?,?,?,?,?,?)",
                [name, body["kind"] as? String ?? "schedule", body["days"] as? String ?? "", body["time"] ?? NSNull(), steps, body["note"] as? String ?? "", ord,
                 (body["continuous"] as? Bool == true || intval(body["continuous"]) != 0) ? 1 : 0])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/psy/practices/([0-9]+)/log$"), method == "POST" {
            let pid = Int(m[1]) ?? -1
            let answers = String(data: (try? json(body["answers"] ?? [])) ?? Data("[]".utf8), encoding: .utf8) ?? "[]"
            let cont = intval((try? db.rows("SELECT continuous FROM practices WHERE id = ?", [pid]))?.first?["continuous"]) != 0
            let date = body["date"] as? String ?? localToday()
            let note = body["note"] as? String ?? ""
            if cont {
                // дневник: ОДНА запись со СТАБИЛЬНЫМ id — UPDATE существующей (не пересоздаём id,
                // иначе keyed-синк плодит записи и затирает). Лишние (legacy по дням) схлопываем.
                if let lid = (try? db.rows("SELECT id FROM practice_log WHERE practice_id = ? ORDER BY id LIMIT 1", [pid]))?.first?["id"] {
                    try db.run("DELETE FROM practice_log WHERE practice_id = ? AND id <> ?", [pid, lid])
                    try db.run("UPDATE practice_log SET note = ?, answers = ?, date = ? WHERE id = ?", [note, answers, date, lid])
                } else {
                    try db.run("INSERT INTO practice_log(practice_id, date, note, answers) VALUES(?,?,?,?)", [pid, date, note, answers])
                }
                return (ok(201), 201)
            }
            // обычная практика: одна запись на день
            try db.run("DELETE FROM practice_log WHERE practice_id = ? AND date = ?", [pid, date])
            try db.run("INSERT INTO practice_log(practice_id, date, note, answers) VALUES(?,?,?,?)", [pid, date, note, answers])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/psy/practices/([0-9]+)$") {
            let id = Int(m[1]) ?? -1
            if method == "PATCH" {
                try patchCols(db, "practices", id, ["name", "kind", "days", "time", "note", "archived", "category", "continuous"], body)
                if body["steps"] != nil {
                    let steps = String(data: (try? json(body["steps"] ?? [])) ?? Data("[]".utf8), encoding: .utf8) ?? "[]"
                    try db.run("UPDATE practices SET steps = ? WHERE id = ?", [steps, id])
                }
                return (ok(), 200)
            }
            if method == "DELETE" { try db.run("DELETE FROM practices WHERE id = ?", [id]); return (ok(), 200) }
        }
        if method == "POST", path == "/api/psy/wheel" {
            if let scores = body["scores"] as? [String: Any] {
                for (areaId, score) in scores {
                    let s = max(1, min(10, Int(num(score).rounded())))
                    try db.run("INSERT INTO wheel_scores(date, area_id, score) VALUES(?,?,?) ON CONFLICT(date, area_id) DO UPDATE SET score = excluded.score",
                        [localToday(), Int(areaId) ?? -1, s])
                }
            }
            return (try json(try psyWheel(db)), 200)
        }
        if let m = match(path, "^/api/psy/areas/([0-9]+)/task$"), method == "POST" {
            do { return (try json(try wheelStepToTask(db, areaId: Int(m[1]) ?? -1)), 201) } catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/psy/areas/([0-9]+)$"), method == "PATCH" {
            try patchAreaStep(db, id: Int(m[1]) ?? -1, body: body); return (ok(), 200)
        }
        if method == "POST", path == "/api/psy/areas" {
            let name = (body["name"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            guard !name.isEmpty else { return (try json(["error": "name required"]), 400) }
            try db.run("INSERT INTO wheel_areas(name, ord) VALUES(?, (SELECT COALESCE(MAX(ord), 0) + 1 FROM wheel_areas))", [name])
            return (try json(try psyWheel(db)), 201)
        }
        if let m = match(path, "^/api/psy/areas/([0-9]+)$"), method == "DELETE" {
            // замеры сектора уходят каскадом (wheel_scores), теги area_id обнуляются (ON DELETE SET NULL)
            try db.run("DELETE FROM wheel_areas WHERE id = ?", [Int(m[1]) ?? -1])
            return (try json(try psyWheel(db)), 200)
        }
        if let m = match(path, "^/api/psy/areas/([0-9]+)/reorder$"), method == "POST" {
            guard let ref = numOpt(body["ref"]).map({ Int($0) }) else { return (try json(["error": "ref required"]), 400) }
            // порядок секторов = порядок сфер (везде ORDER BY ord, id)
            do { try reorderSimple(db, "wheel_areas", id: Int(m[1]) ?? -1, refId: ref, pos: (body["where"] as? String) == "before" ? "before" : "after"); return (try json(try psyWheel(db)), 200) }
            catch { return (errJson(error), 400) }
        }
        if method == "POST", path == "/api/psy/worklog" {
            guard let note = (body["note"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), !note.isEmpty else { return (try json(["error": "note required"]), 400) }
            try db.run("INSERT INTO work_log(date, note) VALUES(?,?)", [localToday(), note]); return (ok(201), 201)
        }
        if let m = match(path, "^/api/psy/worklog/([0-9]+)$"), method == "DELETE" {
            try db.run("DELETE FROM work_log WHERE id = ?", [Int(m[1]) ?? -1]); return (ok(), 200)
        }

        // ----- Трекинг -----
        if method == "POST", path == "/api/track/checkin" {
            let mood = max(1, min(3, Int(num(body["mood"]).rounded())))
            try db.run("INSERT INTO checkins(date, mood, note) VALUES(?,?,?) ON CONFLICT(date) DO UPDATE SET mood = excluded.mood, note = excluded.note",
                [localToday(), mood, body["note"] as? String ?? ""])
            return (ok(), 200)
        }
        if method == "POST", path == "/api/track/metrics" {
            guard let name = name(body) else { return (nameErr(), 400) }
            let ord = nextOrd(db, "SELECT COALESCE(MAX(ord),0)+1 AS o FROM metrics")
            let mid = try db.run("INSERT INTO metrics(name, type, unit, ord, polarity, cadence, source) VALUES(?,?,?,?,?,?,?)",
                [name, body["type"] as? String ?? "number", body["unit"] as? String ?? "", ord, body["polarity"] as? String ?? "plus",
                 body["cadence"] as? String ?? "daily", (body["source"] as? String).flatMap { $0.isEmpty ? nil : $0 }])
            try db.run("DELETE FROM metric_log WHERE metric_id = ?", [mid])   // новая метрика стартует чистой (SQLite переиспользует id удалённых — старые записи не должны прилипнуть)
            return (try json(["id": mid]), 201)
        }
        if let m = match(path, "^/api/track/metrics/([0-9]+)/value$") {
            let mid = Int(m[1]) ?? -1
            let cadence = (try? db.rows("SELECT cadence FROM metrics WHERE id = ?", [mid]))?.first?["cadence"] as? String ?? "daily"
            let op = body["op"] as? String
            // удаление: DELETE-метод ИЛИ POST с op (схема pipboy:// может не пропускать DELETE — POST надёжнее)
            if method == "DELETE" || op == "clear" || op == "del" {
                ensureSyncSchema(db)
                let dates: [String] = (body["date"] as? String).map { [snapISO(cadence, $0)] }
                    ?? ((try? db.rows("SELECT date FROM metric_log WHERE metric_id = ?", [mid]))?.compactMap { $0["date"] as? String } ?? [])
                for d in dates {
                    try db.run("DELETE FROM metric_log WHERE metric_id = ? AND date = ?", [mid, d])
                    // надгробие: чтобы синк с телефона НЕ вернул удалённую запись (metric_log синкается union-ом)
                    try? db.run("INSERT OR REPLACE INTO sync_tombstones(tbl, row_key, deleted_at) VALUES('metric_log', ?, ?)", ["\(mid)|\(d)", isoNow()])
                }
                return (try json(["deleted": dates.count]), 200)
            }
            // дату снапим к ключу периода метрики (день/воскресенье/месяц) → одно значение на период
            let date = (body["date"] as? String).map { snapISO(cadence, $0) } ?? periodKey(cadence)
            try db.run("INSERT INTO metric_log(metric_id, date, value) VALUES(?,?,?) ON CONFLICT(metric_id, date) DO UPDATE SET value = excluded.value",
                [mid, date, num(body["value"])])
            return (ok(), 200)
        }
        if let m = match(path, "^/api/track/metrics/([0-9]+)$") {
            let id = Int(m[1]) ?? -1
            if method == "PATCH" { try patchCols(db, "metrics", id, ["name", "type", "unit", "polarity", "target", "cadence", "source"], body); return (ok(), 200) }
            if method == "DELETE" { try db.run("DELETE FROM metrics WHERE id = ?", [id]); return (ok(), 200) }
        }

        // ----- Настройки -----
        if method == "POST", path == "/api/setting" {
            guard let key = body["key"] as? String, ["activity_month", "monthly_budget", "backup_dir", "focus_order"].contains(key) else {
                return (try json(["error": "unknown key"]), 400)
            }
            try setSetting(db, key, body["value"]); return (ok(), 200)
        }

        // ----- Календарь (события) -----
        if method == "POST", path == "/api/events" {
            guard let title = name(body, "title"),
                  let date = body["date"] as? String, regexTest(date, "^[0-9]{4}-[0-9]{2}-[0-9]{2}$") else {
                return (try json(["error": "title и date обязательны"]), 400)
            }
            try db.run("INSERT INTO events(title, date, time, recur, note) VALUES(?,?,?,?,?)",
                [title, date, body["time"] ?? NSNull(), body["recur"] as? String ?? "none", body["note"] as? String ?? ""])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/events/([0-9]+)/done$"), method == "POST" {
            let id = Int(m[1]) ?? -1
            let date = body["date"] as? String ?? ""
            let has = !(try db.rows("SELECT 1 AS x FROM event_done WHERE event_id = ? AND date = ?", [id, date]).isEmpty)
            if has { try db.run("DELETE FROM event_done WHERE event_id = ? AND date = ?", [id, date]) }
            else { try db.run("INSERT OR IGNORE INTO event_done(event_id, date) VALUES(?,?)", [id, date]) }
            return (try json(["done": !has]), 200)
        }
        if let m = match(path, "^/api/events/([0-9]+)$") {
            let id = Int(m[1]) ?? -1
            if method == "PATCH" { try patchCols(db, "events", id, ["title", "date", "time", "recur", "note"], body); return (ok(), 200) }
            if method == "DELETE" { try db.run("DELETE FROM events WHERE id = ?", [id]); return (ok(), 200) }
        }

        // ----- Корзина -----
        if method == "POST", path == "/api/trash/clear" {
            let n = try db.run("DELETE FROM trash"); _ = n
            return (try json(["cleared": db.changes()]), 200)
        }
        if let m = match(path, "^/api/trash/([0-9]+)/restore$"), method == "POST" {
            return (try restoreTrash(db, id: Int(m[1]) ?? -1), 200)
        }
        if let m = match(path, "^/api/trash/([0-9]+)$"), method == "DELETE" {
            try db.run("DELETE FROM trash WHERE id = ?", [Int(m[1]) ?? -1]); return (ok(), 200)
        }

        // ----- Цели: импорт-блок, связи, объединение, план -----
        if method == "POST", path == "/api/import" {
            guard let text = body["text"] as? String, !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                return (try json(["error": "text required"]), 400)
            }
            return (try json(["imported": try importBlock(db, parentId: numOpt(body["parent_id"]).map { Int($0) }, text: text)]), 201)
        }
        if method == "POST", path == "/api/links" {
            do { try addLink(db, from: intval(body["from_id"]), to: intval(body["to_id"]), type: body["type"] as? String ?? "related"); return (ok(201), 201) }
            catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/links/([0-9]+)$"), method == "DELETE" {
            try db.run("DELETE FROM links WHERE id = ?", [Int(m[1]) ?? -1]); return (ok(), 200)
        }
        if method == "POST", path == "/api/dismiss" {
            let a = intval(body["a"]), b = intval(body["b"]); let lo = min(a, b), hi = max(a, b)
            try db.run("INSERT OR IGNORE INTO dismissed(a, b) VALUES(?,?)", [lo, hi]); return (ok(), 200)
        }
        if method == "POST", path == "/api/merge" {
            do { return (try json(try mergeNodes(db, keepId: intval(body["keep"]), dupId: intval(body["dup"])) ?? [:]), 200) }
            catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/nodes/([0-9]+)/plan$"), method == "POST" {
            do { return (try json(try planPage(db, nodeId: Int(m[1]) ?? -1)), 201) } catch { return (errJson(error), 400) }
        }
        // ----- Трекинг: reorder метрик -----
        if let m = match(path, "^/api/track/metrics/([0-9]+)/reorder$"), method == "POST" {
            guard let ref = numOpt(body["ref_id"]).map({ Int($0) }) else { return (try json(["error": "ref_id"]), 400) }
            do { try reorderSimple(db, "metrics", id: Int(m[1]) ?? -1, refId: ref, pos: (body["where"] as? String) == "before" ? "before" : "after"); return (ok(), 200) }
            catch { return (errJson(error), 400) }
        }
        // ----- Пароли разделов (sha256 UI-замок) -----
        if method == "POST", path == "/api/lock/unlock" {
            if checkPass(db, "lock_pw_hash", body["password"] as? String ?? "") {
                let key = try db.rows("SELECT value FROM settings WHERE key = 'lock_pw_hash'").first?["value"] as? String ?? ""
                return (try json(["ok": true, "key": key]), 200)
            }
            return (try json(["error": "неверный пароль"]), 403)
        }
        if method == "POST", path == "/api/lock/pass" {
            let enabled = try db.lockEnabled()
            if enabled && !checkPass(db, "lock_pw_hash", body["old"] as? String ?? "") {
                return (try json(["error": "неверный текущий пароль"]), 403)
            }
            try setSetting(db, "lock_pw_hash", passOrEmpty(body["password"] as? String))
            return (ok(), 200)
        }
        if method == "POST", path == "/api/psy/unlock" {
            if checkPass(db, "psy_pass_hash", body["password"] as? String ?? "") { return (ok(), 200) }
            return (try json(["error": "неверный пароль"]), 403)
        }
        if method == "POST", path == "/api/psy/pass" {
            let hasPass = try settingNonEmpty(db, "psy_pass_hash")
            if hasPass && !checkPass(db, "psy_pass_hash", body["old"] as? String ?? "") {
                return (try json(["error": "неверный текущий пароль"]), 403)
            }
            try setSetting(db, "psy_pass_hash", passOrEmpty(body["password"] as? String))
            return (ok(), 200)
        }
        // ----- Инфо: ревизия версий, пароль на заметку -----
        if let m = match(path, "^/api/pages/([0-9]+)/revisions/([0-9]+)/restore$"), method == "POST" {
            do { return (try json(try restoreRevision(db, pageId: Int(m[1]) ?? -1, revId: Int(m[2]) ?? -1) ?? [:]), 200) }
            catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/pages/([0-9]+)/lock$"), method == "POST" {
            do { var pg = try lockPage(db, id: Int(m[1]) ?? -1, password: body["password"] as? String ?? "", newContent: body["content"] as? String); pg.removeValue(forKey: "enc"); return (try json(pg), 200) }
            catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/pages/([0-9]+)/unlock$"), method == "POST" {
            do { return (try json(try unlockPage(db, id: Int(m[1]) ?? -1, password: body["password"] as? String ?? "", remove: (body["remove"] as? Bool == true) || intval(body["remove"]) != 0)), 200) }
            catch { return (errJson(error), 403) }
        }
        // ----- Экспорт, импорт Monefy -----
        if method == "POST", path == "/api/export" {
            return (try json(try exportAll(db)), 200)
        }
        if method == "POST", path == "/api/fin/monefy" {
            do { return (try json(["imported": try importMonefy(db, body["csv"] as? String ?? "")]), 201) } catch { return (errJson(error), 400) }
        }

        // ----- Финансы -----
        if method == "POST", path == "/api/backup" {
            return (try json(try backup(db)), 200)
        }
        if let r = try finWrite(method: method, path: path, body: body, db: db) { return r }

        throw Unsupported(path: "\(method) \(path)")
    }

    // Хелперы записи
    private static func ok(_ code: Int = 200) -> Data { (try? json(["ok": true])) ?? Data() }
    private static func nameErr() -> Data { (try? json(["error": "name required"])) ?? Data() }
    private static func errJson(_ e: Error) -> Data { (try? json(["error": "\(e)"])) ?? Data() }
    private static func name(_ body: [String: Any], _ key: String = "name") -> String? {
        let v = (body[key] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines)
        return (v?.isEmpty == false) ? v : nil
    }
    private static func nextOrd(_ db: Database, _ sql: String) -> Int {
        ((try? db.rows(sql))?.first?["o"] as? Int) ?? 1
    }
    static func patchCols(_ db: Database, _ table: String, _ id: Int, _ cols: [String], _ body: [String: Any]) throws {
        for k in cols where body[k] != nil {
            // accounts.balance: трогаем и дату обновления
            if table == "accounts" && k == "balance" {
                try db.run("UPDATE accounts SET balance = ?, balance_updated_at = datetime('now','localtime') WHERE id = ?", [body[k], id])
            } else {
                try db.run("UPDATE \(table) SET \(k) = ? WHERE id = ?", [body[k], id])
            }
        }
        // steps.status → синк привязанной задачи
        if table == "steps", body["status"] != nil {
            if let taskId = try db.rows("SELECT task_id FROM steps WHERE id = ?", [id]).first?["task_id"] as? Int {
                let st = (body["status"] as? String) == "done" ? "done" : "todo"
                try db.run("UPDATE nodes SET status = ?, updated_at = datetime('now','localtime') WHERE id = ? AND kind = 'task'", [st, taskId])
            }
        }
    }
    static func setSetting(_ db: Database, _ key: String, _ value: Any?) throws {
        let v: String
        if let s = value as? String { v = s }
        else if let i = value as? Int { v = String(i) }
        else if let d = value as? Double { v = d == d.rounded() ? String(Int(d)) : String(d) }
        else { v = "" }
        try db.run("INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value", [key, v])
    }
    static func toggleRoutineToday(_ db: Database, _ id: Int) throws -> Bool {
        let t = localToday()
        let has = !(try db.rows("SELECT 1 AS x FROM routine_log WHERE routine_id = ? AND date = ?", [id, t]).isEmpty)
        if has { try db.run("DELETE FROM routine_log WHERE routine_id = ? AND date = ?", [id, t]) }
        else { try db.run("INSERT INTO routine_log(routine_id, date) VALUES(?,?)", [id, t]) }
        return !has
    }

    // ----- Пароли разделов (sha256 'pipboy:'+pw) -----
    private static func passHash(_ s: String) -> String {
        SHA256.hash(data: Data(("pipboy:" + s).utf8)).map { String(format: "%02x", $0) }.joined()
    }
    static func checkPass(_ db: Database, _ key: String, _ pw: String) -> Bool {
        let h = (((try? db.rows("SELECT value FROM settings WHERE key = ?", [key]))?.first?["value"]) as? String) ?? ""
        return h.isEmpty || h == passHash(pw)
    }
    private static func passOrEmpty(_ pw: String?) -> String { (pw?.isEmpty == false) ? passHash(pw!) : "" }

    // ----- Импорт-блок целей -----
    static func importBlock(_ db: Database, parentId: Int?, text: String) throws -> Int {
        let rows = parseOutline(text)
        var stack: [(level: Int, id: Int?)] = [(-1, parentId)]
        var count = 0
        for r in rows {
            while stack.count > 1 && stack.last!.level >= r.level { stack.removeLast() }
            let id = try insertNode(db, parentId: stack.last!.id, title: r.title, note: "", isCategory: 0)
            stack.append((r.level, id)); count += 1
        }
        return count
    }
    private static func parseOutline(_ text: String) -> [(level: Int, title: String)] {
        var items: [(indent: Int, title: String)] = []
        for raw in text.replacingOccurrences(of: "\r", with: "").split(separator: "\n", omittingEmptySubsequences: false) {
            let line = String(raw)
            if line.trimmingCharacters(in: .whitespaces).isEmpty { continue }
            let indent = line.prefix { $0 == " " || $0 == "\t" }.reduce(0) { $0 + ($1 == "\t" ? 4 : 1) }
            var title = line.trimmingCharacters(in: .whitespaces)
            if let r = title.range(of: "^(?:[0-9]+[.)]|[-*•◦▪‣o])\\s+", options: .regularExpression) { title.removeSubrange(r) }
            title = title.trimmingCharacters(in: .whitespaces)
            if !title.isEmpty { items.append((indent, title)) }
        }
        let levels = Array(Set(items.map { $0.indent })).sorted()
        return items.map { (levels.firstIndex(of: $0.indent) ?? 0, $0.title) }
    }

    // ----- Связи / объединение -----
    static func addLink(_ db: Database, from: Int, to: Int, type: String) throws {
        if from == to { throw Unsupported(path: "self-link") }
        if type == "blocks", try reaches(db, from: to, to: from) { throw Unsupported(path: "cycle") }
        try db.run("INSERT OR IGNORE INTO links(from_id, to_id, type) VALUES(?,?,?)", [from, to, type])
    }
    private static func reaches(_ db: Database, from: Int, to: Int) throws -> Bool {
        !(try db.rows("WITH RECURSIVE r(id) AS (SELECT to_id FROM links WHERE from_id = ? AND type = 'blocks' UNION SELECT l.to_id FROM links l JOIN r ON l.from_id = r.id AND l.type = 'blocks') SELECT 1 FROM r WHERE id = ? LIMIT 1", [from, to]).isEmpty)
    }
    static func mergeNodes(_ db: Database, keepId: Int, dupId: Int) throws -> [String: Any]? {
        if keepId == dupId { throw Unsupported(path: "same node") }
        guard let keep = try getNode(db, keepId), let dup = try getNode(db, dupId) else { throw Unsupported(path: "not found") }
        for ch in try db.rows("SELECT id FROM nodes WHERE parent_id = ? ORDER BY ord", [dupId]) {
            let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM nodes WHERE parent_id IS ?", [keepId]).first?["o"]))
            try db.run("UPDATE nodes SET parent_id = ?, ord = ? WHERE id = ?", [keepId, ord, intval(ch["id"])])
        }
        for l in try db.rows("SELECT * FROM links WHERE from_id = ? OR to_id = ?", [dupId, dupId]) {
            let from = intval(l["from_id"]) == dupId ? keepId : intval(l["from_id"])
            let to = intval(l["to_id"]) == dupId ? keepId : intval(l["to_id"])
            try db.run("DELETE FROM links WHERE id = ?", [intval(l["id"])])
            if from != to { try db.run("INSERT OR IGNORE INTO links(from_id, to_id, type) VALUES(?,?,?)", [from, to, l["type"] ?? "related"]) }
        }
        var fields: [String: Any] = [:]
        let kDue = keep["due_date"] as? String, dDue = dup["due_date"] as? String
        if let dd = dDue, !dd.isEmpty, (kDue?.isEmpty != false || dd < (kDue ?? "~")) { fields["due_date"] = dd }
        let kPr = keep["priority"] as? String, dPr = dup["priority"] as? String
        if let dp = dPr, !dp.isEmpty, (kPr?.isEmpty != false || dp < (kPr ?? "~")) { fields["priority"] = dp }
        if (keep["kind"] is NSNull || keep["kind"] == nil), !(dup["kind"] is NSNull), dup["kind"] != nil { fields["kind"] = dup["kind"]!; fields["status"] = dup["status"] ?? NSNull() }
        fields["note"] = [keep["note"] as? String ?? "", "[объединено] \(dup["title"] as? String ?? "")", dup["note"] as? String ?? ""].filter { !$0.isEmpty }.joined(separator: "\n")
        _ = try updateNode(db, id: keepId, fields: fields)
        try db.run("DELETE FROM node_fts WHERE rowid = ?", [dupId])
        try db.run("DELETE FROM nodes WHERE id = ?", [dupId])
        return try getNode(db, keepId)
    }
    static func planPage(_ db: Database, nodeId: Int) throws -> [String: Any] {
        if let existing = try db.rows("SELECT * FROM pages WHERE node_id = ?", [nodeId]).first { return existing }
        guard let node = try getNode(db, nodeId) else { throw Unsupported(path: "node not found") }
        let rootId: Int
        if let root = try db.rows("SELECT id FROM pages WHERE title = 'Планы задач' AND parent_id IS NULL").first { rootId = intval(root["id"]) }
        else { rootId = intval(try addPage(db, title: "Планы задач", body: [:])["id"]) }
        let title = node["title"] as? String ?? "", noteV = node["note"] as? String ?? ""
        let content = "# План: \(title)\n\nКонтекст: \(noteV.isEmpty ? "—" : noteV)\n\n## Рассуждение\n\n- \n\n## Шаги\n\n- [ ] \n"
        return try addPage(db, title: title, body: ["parent_id": rootId, "node_id": nodeId, "content": content])
    }
    static func restoreRevision(_ db: Database, pageId: Int, revId: Int) throws -> [String: Any]? {
        guard let rev = try db.rows("SELECT * FROM page_revisions WHERE id = ? AND page_id = ?", [revId, pageId]).first else { throw Unsupported(path: "ревизия не найдена") }
        return try patchPage(db, id: pageId, body: ["content": rev["content"] ?? ""])
    }
    static func reorderSimple(_ db: Database, _ table: String, id: Int, refId: Int, pos: String) throws {
        if id == refId { return }
        var all = try db.rows("SELECT id FROM \(table) ORDER BY ord, id").compactMap { $0["id"] as? Int }.filter { $0 != id }
        guard let at = all.firstIndex(of: refId) else { throw Unsupported(path: "сосед не найден") }
        all.insert(id, at: at + (pos == "after" ? 1 : 0))
        for (i, mid) in all.enumerated() { try db.run("UPDATE \(table) SET ord = ? WHERE id = ?", [i + 1, mid]) }
    }

    // ----- Пароль на заметку (AES-GCM + scrypt, см. Crypto.swift) -----
    static func lockPage(_ db: Database, id: Int, password: String, newContent: String?) throws -> [String: Any] {
        guard let p = try getPage(db, id) else { throw Unsupported(path: "not found") }
        if password.isEmpty { throw Unsupported(path: "пустой пароль") }
        let content: String
        if intval(p["locked"]) != 0 {
            let old = try PageCrypto.decrypt(password: password, encStr: p["enc"] as? String ?? "")
            content = newContent ?? old
        } else { content = newContent ?? (p["content"] as? String ?? "") }
        let enc = try PageCrypto.encrypt(password: password, text: content)
        try db.run("UPDATE pages SET enc = ?, locked = 1, content = '', updated_at = datetime('now','localtime') WHERE id = ?", [enc, id])
        try db.run("DELETE FROM page_fts WHERE rowid = ?", [id])
        return try getPage(db, id) ?? [:]
    }
    static func unlockPage(_ db: Database, id: Int, password: String, remove: Bool) throws -> [String: Any] {
        guard let p = try getPage(db, id), intval(p["locked"]) != 0 else { throw Unsupported(path: "страница не под паролем") }
        let content = try PageCrypto.decrypt(password: password, encStr: p["enc"] as? String ?? "")
        if remove {
            try db.run("UPDATE pages SET enc = NULL, locked = 0, content = ?, updated_at = datetime('now','localtime') WHERE id = ?", [content, id])
            try db.run("INSERT INTO page_fts(rowid, title_norm, content_norm) VALUES(?,?,?)", [id, norm(p["title"] as? String ?? ""), norm(content)])
        }
        return ["content": content]
    }

    // ----- Экспорт / импорт Monefy -----
    static func exportAll(_ db: Database) throws -> [String: Any] {
        #if os(macOS)
        let dir = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Downloads/cladue/app/export", isDirectory: true)
        #else
        let dir = try FileManager.default.url(for: .documentDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
            .appendingPathComponent("export", isDirectory: true)
        #endif
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let tables = ["nodes", "links", "accounts", "portfolio_items", "obligations", "passive_income", "debts", "transactions",
                      "events", "routines", "people", "pages", "practices", "wheel_areas", "wheel_scores", "metrics", "forecasts",
                      "properties", "budget_items", "settings", "rates",
                      "routine_log", "metric_log", "practice_log", "contact_log"]   // логи отметок → стрики/история в трекере
        var dump: [String: Any] = [:]
        for t in tables { dump[t] = (try? db.rows("SELECT * FROM \(t)")) ?? [] }
        let file = dir.appendingPathComponent("data.json")
        try JSONSerialization.data(withJSONObject: dump, options: [.prettyPrinted]).write(to: file)
        #if os(macOS)
        NSWorkspace.shared.open(dir)   // открыть папку в Finder (на iOS — позже share sheet)
        #endif
        return ["dir": dir.path, "files": [file.path]]
    }
    static func importMonefy(_ db: Database, _ csv: String) throws -> Int {
        let lines = csv.replacingOccurrences(of: "\r", with: "").split(separator: "\n").map(String.init).filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }
        if lines.count < 2 { return 0 }
        let delim: Character = lines[0].filter { $0 == ";" }.count >= lines[0].filter { $0 == "," }.count ? ";" : ","
        func split(_ l: String) -> [String] { l.split(separator: delim, omittingEmptySubsequences: false).map { $0.trimmingCharacters(in: CharacterSet(charactersIn: "\" ")) } }
        let head = split(lines[0]).map { $0.lowercased() }
        func col(_ names: [String]) -> Int { head.firstIndex(where: { h in names.contains(where: { h.contains($0) }) }) ?? -1 }
        let iDate = col(["date", "дата"]), iAmount = col(["amount", "сумма"]), iCat = col(["category", "категория"]), iCur = col(["currency", "валюта"]), iNote = col(["description", "note", "описание"])
        if iDate < 0 || iAmount < 0 { throw Unsupported(path: "не нашёл колонки date/amount") }
        var count = 0
        for line in lines.dropFirst() {
            let c = split(line)
            guard iAmount < c.count, iDate < c.count,
                  let amount = Double(c[iAmount].replacingOccurrences(of: " ", with: "").replacingOccurrences(of: ",", with: ".")),
                  let date = parseAnyDate(c[iDate]) else { continue }
            try finAdd(db, "tx", [
                "date": date, "amount": abs(amount), "direction": amount < 0 ? "expense" : "income",
                "category": (iCat >= 0 && iCat < c.count && !c[iCat].isEmpty) ? c[iCat] : "прочее",
                "currency": (iCur >= 0 && iCur < c.count && !c[iCur].isEmpty) ? normCur(c[iCur]) : "€",
                "note": (iNote >= 0 && iNote < c.count) ? c[iNote] : "", "source": "monefy"])
            count += 1
        }
        return count
    }
    private static func parseAnyDate(_ s: String) -> String? {
        let t = s.trimmingCharacters(in: .whitespaces)
        if regexTest(t, "^[0-9]{4}-[0-9]{2}-[0-9]{2}") { return String(t.prefix(10)) }
        let parts = t.split(whereSeparator: { $0 == "/" || $0 == "." || $0 == "-" }).map(String.init)
        if parts.count >= 3, let d = Int(parts[0]), let m = Int(parts[1]), let y = Int(parts[2]), y > 1900 {
            return String(format: "%04d-%02d-%02d", y, m, d)
        }
        return nil
    }
    private static func normCur(_ s: String) -> String { (s.uppercased().contains("USD") || s.contains("$")) ? "$" : "€" }

    // ----- Узлы-помощники -----
    static func addChild(_ db: Database, parentId: Int?, title: String) throws -> [String: Any]? {
        let id = try insertNode(db, parentId: parentId, title: title, note: "", isCategory: 0)
        return try getNode(db, id)
    }
    static func listCategories(_ db: Database) throws -> [[String: Any]] {
        try db.rows("SELECT * FROM nodes WHERE is_category = 1 ORDER BY parent_id NULLS FIRST, ord")
    }

    // ----- Инфо: страницы (порт notes.js) -----
    static func getPage(_ db: Database, _ id: Int) throws -> [String: Any]? {
        try db.rows("SELECT * FROM pages WHERE id = ?", [id]).first
    }
    static func addPage(_ db: Database, title: String, body: [String: Any]) throws -> [String: Any] {
        let parent = numOpt(body["parent_id"]).map { Int($0) }
        let content = body["content"] as? String ?? ""
        let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM pages WHERE parent_id IS ?", [parent]).first?["o"]))
        let id = try db.run("INSERT INTO pages(parent_id, ord, title, content, node_id, updated_at) VALUES(?,?,?,?,?, datetime('now','localtime'))",
            [parent, ord, title, content, numOpt(body["node_id"]).map { Int($0) }])
        try db.run("INSERT INTO page_fts(rowid, title_norm, content_norm) VALUES(?,?,?)", [id, norm(title), norm(content)])
        return try getPage(db, id) ?? [:]
    }
    static func patchPage(_ db: Database, id: Int, body: [String: Any]) throws -> [String: Any]? {
        let before = try getPage(db, id)
        let locked = intval(before?["locked"]) != 0
        if locked && body["content"] != nil { throw Unsupported(path: "страница под паролем — сохраняй через lock") }
        if body["content"] != nil, let before, !locked {
            let newC = body["content"] as? String ?? "", oldC = before["content"] as? String ?? ""
            if oldC != newC && !oldC.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                var recent = false
                if let last = try db.rows("SELECT saved_at FROM page_revisions WHERE page_id = ? ORDER BY id DESC LIMIT 1", [id]).first?["saved_at"] as? String,
                   let d = sqliteDate(last) { recent = Date().timeIntervalSince(d) < 600 }
                if !recent {
                    try db.run("INSERT INTO page_revisions(page_id, content) VALUES(?,?)", [id, oldC])
                    try db.run("DELETE FROM page_revisions WHERE page_id = ? AND id NOT IN (SELECT id FROM page_revisions WHERE page_id = ? ORDER BY id DESC LIMIT 20)", [id, id])
                }
            }
        }
        for k in ["title", "content"] where body[k] != nil {
            try db.run("UPDATE pages SET \(k) = ?, updated_at = datetime('now','localtime') WHERE id = ?", [body[k], id])
        }
        if (body["title"] != nil || body["content"] != nil) && !locked, let p = try getPage(db, id) {
            try db.run("UPDATE page_fts SET title_norm = ?, content_norm = ? WHERE rowid = ?",
                [norm(p["title"] as? String ?? ""), norm(p["content"] as? String ?? ""), id])
        }
        return try getPage(db, id)
    }
    static func movePage(_ db: Database, id: Int, parent: Int?) throws -> [String: Any]? {
        if let p = parent {
            if p == id { throw Unsupported(path: "self-parent") }
            let desc = try db.rows("WITH RECURSIVE r(x) AS (SELECT id FROM pages WHERE parent_id = ? UNION SELECT p.id FROM pages p JOIN r ON p.parent_id = r.x) SELECT 1 FROM r WHERE x = ? LIMIT 1", [id, p])
            if !desc.isEmpty { throw Unsupported(path: "descendant") }
        }
        let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM pages WHERE parent_id IS ?", [parent]).first?["o"]))
        try db.run("UPDATE pages SET parent_id = ?, ord = ? WHERE id = ?", [parent, ord, id])
        return try getPage(db, id)
    }
    static func reorderPage(_ db: Database, id: Int, refId: Int, pos: String) throws {
        if id == refId { throw Unsupported(path: "self") }
        guard let ref = try db.rows("SELECT id, parent_id FROM pages WHERE id = ?", [refId]).first else { throw Unsupported(path: "сосед не найден") }
        let rp = numOpt(ref["parent_id"]).map { Int($0) }
        if rp == id { throw Unsupported(path: "descendant") }
        if let rpp = rp {
            let desc = try db.rows("WITH RECURSIVE r(x) AS (SELECT id FROM pages WHERE parent_id = ? UNION SELECT p.id FROM pages p JOIN r ON p.parent_id = r.x) SELECT 1 FROM r WHERE x = ? LIMIT 1", [id, rpp])
            if !desc.isEmpty { throw Unsupported(path: "descendant") }
        }
        var siblings = try db.rows("SELECT id FROM pages WHERE parent_id IS ? ORDER BY ord, id", [rp]).compactMap { $0["id"] as? Int }.filter { $0 != id }
        if let idx = siblings.firstIndex(of: refId) { siblings.insert(id, at: idx + (pos == "after" ? 1 : 0)) } else { siblings.append(id) }
        try db.run("UPDATE pages SET parent_id = ? WHERE id = ?", [rp, id])
        for (i, sid) in siblings.enumerated() { try db.run("UPDATE pages SET ord = ? WHERE id = ?", [i + 1, sid]) }
    }
    static func delPage(_ db: Database, id: Int) throws -> [String: Any] {
        guard let root = try getPage(db, id) else { return ["count": 0, "trash_id": NSNull()] }
        let rows = try db.rows("WITH RECURSIVE r(x, depth) AS (SELECT ?, 0 UNION ALL SELECT p.id, r.depth+1 FROM pages p JOIN r ON p.parent_id = r.x) SELECT p.*, r.depth AS _depth FROM r JOIN pages p ON p.id = r.x ORDER BY r.depth, p.ord", [id])
        let label = "▤ " + (root["title"] as? String ?? "") + (rows.count > 1 ? " (+\(rows.count - 1) подстр.)" : "")
        let payload = String(data: try json(["rows": rows]), encoding: .utf8) ?? "{}"
        let trashId = try db.run("INSERT INTO trash(kind, label, payload) VALUES(?,?,?)", ["pages", label, payload])
        for r in rows { try db.run("DELETE FROM page_fts WHERE rowid = ?", [intval(r["id"])]) }
        for r in rows { try db.run("DELETE FROM attachments WHERE page_id = ?", [intval(r["id"])]) }
        try db.run("DELETE FROM pages WHERE id = ?", [id])
        return ["count": rows.count, "trash_id": trashId]
    }

    // Вложение страницы Инфо → бинарь (base64 → Data) + MIME. nil, если путь не про вложение или его нет.
    static func attachmentBinary(_ db: Database, path: String) throws -> (Data, String)? {
        guard let m = match(path, "^/api/attachments/([0-9]+)$") else { return nil }
        guard let row = try db.rows("SELECT name, mime, data FROM attachments WHERE id = ?", [Int(m[1]) ?? -1]).first
        else { return nil }
        let mime = row["mime"] as? String ?? "application/octet-stream"
        let data = Data(base64Encoded: row["data"] as? String ?? "") ?? Data()
        return (data, mime)
    }
    private static func sqliteDate(_ s: String) -> Date? {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        f.timeZone = TimeZone(identifier: "UTC"); f.locale = Locale(identifier: "en_US_POSIX")
        return f.date(from: s)
    }

    // ----- Психология: сектор колеса → задача, правка шага -----
    private static let AREA_CAT: [String: String] = ["Работа": "Работа", "Семья и дети": "Семья", "Партнёр": "Семья",
        "Саморазвитие и обучение": "Развитие", "Здоровье и спорт": "Здоровье", "Социализация": "Жизнь", "Дом": "Жизнь",
        "Деньги и инвестиции": "Финансы", "Отдых и хобби": "Отдых", "Перспективы будущего": "Глобальные"]
    static func patchAreaStep(_ db: Database, id: Int, body: [String: Any]) throws {
        try patchCols(db, "wheel_areas", id, ["name", "ideal", "current_desc", "next_desc", "step"], body)
        if let step = (body["step"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines), !step.isEmpty {
            let areaName = try db.rows("SELECT name FROM wheel_areas WHERE id = ?", [id]).first?["name"] as? String ?? ""
            for t in try db.rows("SELECT id FROM nodes WHERE is_category = 0 AND note LIKE ? AND (status IS NULL OR status != 'done')", ["%сектор «\(areaName)»%"]) {
                _ = try updateNode(db, id: intval(t["id"]), fields: ["title": step])
            }
        }
    }
    static func wheelStepToTask(_ db: Database, areaId: Int) throws -> Data {
        guard let area = try db.rows("SELECT * FROM wheel_areas WHERE id = ?", [areaId]).first else { throw Unsupported(path: "сектор не найден") }
        let step = (area["step"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if step.isEmpty { throw Unsupported(path: "у сектора нет шага — сначала задай его") }
        let areaName = area["name"] as? String ?? ""
        let cats = try listCategories(db)
        let target = AREA_CAT[areaName].flatMap { k in cats.first { ($0["title"] as? String ?? "").contains(k) } }
            ?? cats.first { ($0["title"] as? String ?? "").contains("Инбокс") }
        guard let target else { throw Unsupported(path: "категория не найдена") }
        let targetId = intval(target["id"])
        if let dup = try db.rows("SELECT id FROM nodes WHERE is_category = 0 AND title = ? AND parent_id = ? AND (status IS NULL OR status != 'done')", [step, targetId]).first {
            return try json(["node": try getNode(db, intval(dup["id"])) ?? [:], "category": target["title"] ?? NSNull(), "existed": true])
        }
        let node = try addChild(db, parentId: targetId, title: step) ?? [:]
        _ = try updateNode(db, id: intval(node["id"]), fields: ["kind": "task", "priority": "P2", "note": "шаг колеса · сектор «\(areaName)»"])
        return try json(["node": try getNode(db, intval(node["id"])) ?? [:], "category": target["title"] ?? NSNull(), "existed": false])
    }

    // ----- Корзина: восстановление -----
    static func restoreTrash(_ db: Database, id: Int) throws -> Data {
        guard let row = try db.rows("SELECT * FROM trash WHERE id = ?", [id]).first else { return try json(["error": "not found"]) }
        let kind = row["kind"] as? String ?? "nodes"
        let payload = ((try? JSONSerialization.jsonObject(with: Data((row["payload"] as? String ?? "{}").utf8))) as? [String: Any]) ?? [:]
        let newId = kind == "pages" ? try restorePages(db, payload) : try restoreNodes(db, payload)
        try db.run("DELETE FROM trash WHERE id = ?", [id])
        return try json(["restored": newId.map { $0 as Any } ?? NSNull(), "kind": kind])
    }
    static func restoreNodes(_ db: Database, _ payload: [String: Any]) throws -> Int? {
        let rows = payload["rows"] as? [[String: Any]] ?? []
        var map: [Int: Int] = [:]
        let inboxId = (try db.rows("SELECT id FROM nodes WHERE is_category = 1 AND title LIKE '%Инбокс%'").first).map { intval($0["id"]) }
        for r in rows {
            let origParent = numOpt(r["parent_id"]).map { Int($0) }
            var parent: Int? = origParent.flatMap { map[$0] }
            if parent == nil, let op = origParent { parent = (try getNode(db, op) != nil) ? op : inboxId }
            let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM nodes WHERE parent_id IS ?", [parent]).first?["o"]))
            let newId = try db.run("INSERT INTO nodes(parent_id, ord, title, note, is_category, kind, status, priority, due_date, answer, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?, datetime('now','localtime'))",
                [parent, ord, r["title"] ?? "", r["note"] ?? "", intval(r["is_category"]), r["kind"] ?? NSNull(), r["status"] ?? NSNull(), r["priority"] ?? NSNull(), r["due_date"] ?? NSNull(), r["answer"] ?? NSNull()])
            map[intval(r["id"])] = newId
            try db.run("INSERT INTO node_fts(rowid, title_norm, note_norm) VALUES(?,?,?)", [newId, norm(r["title"] as? String ?? ""), norm(r["note"] as? String ?? "")])
        }
        for l in (payload["links"] as? [[String: Any]] ?? []) {
            let fromId = intval(l["from_id"]), toId = intval(l["to_id"])
            let from: Int?
            if let mapped = map[fromId] { from = mapped } else { from = (try getNode(db, fromId) != nil) ? fromId : nil }
            let to: Int?
            if let mapped = map[toId] { to = mapped } else { to = (try getNode(db, toId) != nil) ? toId : nil }
            if let from, let to, from != to {
                try db.run("INSERT OR IGNORE INTO links(from_id, to_id, type) VALUES(?,?,?)", [from, to, l["type"] ?? "related"])
            }
        }
        for s in (payload["stepRefs"] as? [[String: Any]] ?? []) {
            if let nt = map[intval(s["task_id"])] { try db.run("UPDATE steps SET task_id = ? WHERE id = ? AND task_id IS NULL", [nt, intval(s["step_id"])]) }
        }
        return rows.first.flatMap { map[intval($0["id"])] }
    }
    static func restorePages(_ db: Database, _ payload: [String: Any]) throws -> Int? {
        let rows = payload["rows"] as? [[String: Any]] ?? []
        var map: [Int: Int] = [:]
        for r in rows {
            let origParent = numOpt(r["parent_id"]).map { Int($0) }
            var parent: Int? = origParent.flatMap { map[$0] }
            if parent == nil, let op = origParent { parent = (try getPage(db, op) != nil) ? op : nil }
            let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM pages WHERE parent_id IS ?", [parent]).first?["o"]))
            let newId = try db.run("INSERT INTO pages(parent_id, ord, title, content, node_id, locked, enc, updated_at) VALUES(?,?,?,?,?,?,?, datetime('now','localtime'))",
                [parent, ord, r["title"] ?? "", r["content"] ?? "", r["node_id"] ?? NSNull(), intval(r["locked"]), r["enc"] ?? NSNull()])
            map[intval(r["id"])] = newId
            if intval(r["locked"]) == 0 {
                try db.run("INSERT INTO page_fts(rowid, title_norm, content_norm) VALUES(?,?,?)", [newId, norm(r["title"] as? String ?? ""), norm(r["content"] as? String ?? "")])
            }
        }
        return rows.first.flatMap { map[intval($0["id"])] }
    }

    // ----- Бэкап зашифрованной базы (копия файла, последние 20) -----
    static func backup(_ db: Database) throws -> [String: Any] {
        let fm = FileManager.default
        let src = try Database.fileURL()
        let dir = src.deletingLastPathComponent().appendingPathComponent("backups", isDirectory: true)
        try fm.createDirectory(at: dir, withIntermediateDirectories: true)
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd_HH-mm"; f.locale = Locale(identifier: "en_US_POSIX")
        let stamp = f.string(from: Date())
        let dst = dir.appendingPathComponent("pipboy-\(stamp).db")
        try? fm.removeItem(at: dst)
        try fm.copyItem(at: src, to: dst)
        let all = ((try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)) ?? [])
            .filter { $0.pathExtension == "db" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
        if all.count > 20 { for old in all.prefix(all.count - 20) { try? fm.removeItem(at: old) } }
        if let ext = try db.rows("SELECT value FROM settings WHERE key='backup_dir'").first?["value"] as? String, !ext.isEmpty {
            let extDir = URL(fileURLWithPath: ext)
            try? fm.createDirectory(at: extDir, withIntermediateDirectories: true)
            try? fm.copyItem(at: src, to: extDir.appendingPathComponent("pipboy-\(stamp).db"))
        }
        backupOffsite(src, stamp)   // + оффсайт-копия в iCloud Drive
        return ["file": dst.path]
    }

    // ----- Курсы тикеров: единственное, что покидает машину (по кнопке) -----
    private static func httpGet(_ urlStr: String) -> Data? {
        guard let url = URL(string: urlStr) else { return nil }
        var req = URLRequest(url: url, timeoutInterval: 8)
        req.setValue("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", forHTTPHeaderField: "User-Agent")
        req.setValue("application/json,text/csv,*/*", forHTTPHeaderField: "Accept")
        var out: Data?
        let sem = DispatchSemaphore(value: 0)
        URLSession.shared.dataTask(with: req) { d, resp, _ in
            if let http = resp as? HTTPURLResponse, http.statusCode == 200 { out = d }
            sem.signal()
        }.resume()
        _ = sem.wait(timeout: .now() + 10)
        return out
    }
    private static func jsonGet(_ urlStr: String) -> Any? {
        httpGet(urlStr).flatMap { try? JSONSerialization.jsonObject(with: $0) }
    }
    private static func anyNum(_ v: Any?) -> Double? {
        if let d = v as? Double { return d }
        if let i = v as? Int { return Double(i) }
        if let s = v as? String { return Double(s) }
        return nil
    }
    private static func dig(_ obj: Any?, _ path: [Any]) -> Double? {
        var cur = obj
        for k in path {
            if let key = k as? String { cur = (cur as? [String: Any])?[key] }
            else if let idx = k as? Int { let arr = cur as? [Any]; cur = (arr != nil && idx < arr!.count) ? arr![idx] : nil }
        }
        return anyNum(cur)
    }
    private static func stooq(_ sym: String) -> Double? {
        guard let d = httpGet("https://stooq.com/q/l/?s=\(sym)&f=sd2t2ohlcv&h&e=csv"),
              let text = String(data: d, encoding: .utf8) else { return nil }
        let lines = text.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "\n")
        guard lines.count >= 2 else { return nil }
        let cols = lines[1].split(separator: ",", omittingEmptySubsequences: false)
        return cols.count > 6 ? Double(cols[6]) : nil
    }
    static func ratesRefresh(_ db: Database) throws -> Data {
        var errors: [String] = []
        let labels = ["XAUUSD": "Золото", "EURUSD": "EUR/USD", "BTCUSD": "BTC", "SCHD": "SCHD", "IVV": "IVV", "VHT": "VHT"]
        func firstOf(_ srcs: [() -> Double?]) -> Double? {
            for s in srcs { if let p = s(), p.isFinite, p > 0 { return p } }
            return nil
        }
        var sources: [(String, [() -> Double?])] = [
            ("EURUSD", [
                { dig(jsonGet("https://api.frankfurter.app/latest?from=EUR&to=USD"), ["rates", "USD"]) },
                { dig(jsonGet("https://open.er-api.com/v6/latest/EUR"), ["rates", "USD"]) },
                { stooq("eurusd") }]),
            ("BTCUSD", [
                { dig(jsonGet("https://api.coinbase.com/v2/prices/BTC-USD/spot"), ["data", "amount"]) },
                { dig(jsonGet("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"), ["bitcoin", "usd"]) },
                { stooq("btcusd") }]),
            ("XAUUSD", [
                { dig(jsonGet("https://api.coingecko.com/api/v3/simple/price?ids=pax-gold&vs_currencies=usd"), ["pax-gold", "usd"]) },
                { stooq("xauusd") }]),
        ]
        for sym in ["SCHD", "IVV", "VHT"] {
            sources.append((sym, [
                { dig(jsonGet("https://query1.finance.yahoo.com/v8/finance/chart/\(sym)?range=1d&interval=1d"), ["chart", "result", 0, "meta", "regularMarketPrice"]) },
                { stooq(sym.lowercased() + ".us") }]))
        }
        // запросы по символам — параллельно (иначе серийная очередь висит до ~30с)
        var prices: [String: Double] = [:]
        let lock = NSLock()
        DispatchQueue.concurrentPerform(iterations: sources.count) { idx in
            let (sym, srcs) = sources[idx]
            if let p = firstOf(srcs) { lock.lock(); prices[sym] = p; lock.unlock() }
        }
        for (sym, _) in sources {
            guard let price = prices[sym] else { errors.append("\(sym): нет ответа"); continue }
            let prev = anyNum(try db.rows("SELECT price FROM rates WHERE symbol = ?", [sym]).first?["price"])
            let chg: Any = (prev != nil && prev! != 0) ? (price - prev!) / prev! * 100 : NSNull()
            try db.run("INSERT INTO rates(symbol, label, price, change_pct, updated_at) VALUES(?,?,?,?,datetime('now','localtime')) ON CONFLICT(symbol) DO UPDATE SET price = excluded.price, change_pct = excluded.change_pct, updated_at = excluded.updated_at",
                [sym, labels[sym] ?? sym, price, chg])
        }
        let rates = try db.rows("SELECT * FROM rates")
        if rates.allSatisfy({ $0["price"] is NSNull || $0["price"] == nil }) {
            return try json(["error": "ни один источник не ответил: " + errors.joined(separator: "; ")])
        }
        return try json(["rates": rates, "errors": errors])
    }

    // ----- Финансы: запись -----
    private static let finTable = ["accounts": "accounts", "classes": "portfolio_classes", "steps": "steps",
        "obligations": "obligations", "items": "portfolio_items", "tx": "transactions", "debts": "debts", "income": "passive_income",
        "budget": "budget_items", "tgt": "target_items", "move": "target_moves"]
    private static let finCols: [String: [String]] = [
        "accounts": ["name", "type", "currency", "note", "balance"],
        "classes": ["name", "value", "target_pct", "note"],
        "steps": ["kind", "title", "amount", "planned_date", "condition", "status", "note"],
        "obligations": ["name", "amount", "currency", "period", "next_date", "remind_days", "kind", "note", "due_time"],
        "items": ["name", "buy_value", "value", "target_value", "currency", "is_loan", "loan_due", "asset_type", "qty", "rate_symbol", "note", "region"],
        "tx": ["date", "amount", "currency", "direction", "category", "note"],
        "debts": ["name", "amount", "currency", "direction", "due_date", "note"],
        "income": ["name", "amount", "currency", "period", "next_date", "note", "principal", "rate", "rate_period", "asset_type"],
        "budget": ["name", "amount", "currency", "direction", "ord", "month"],
        "tgt": ["name", "value", "buy_value", "target_value", "currency", "asset_type", "qty", "rate_symbol", "note", "kind", "region"],
        "move": ["from_id", "to_id", "amount"]]

    static func finWrite(method: String, path: String, body: [String: Any], db: Database) throws -> (Data, Int)? {
        if method == "POST", path == "/api/rates/refresh" { return (try ratesRefresh(db), 200) }
        if let m = match(path, "^/api/fin/move/([0-9]+)$"), method == "DELETE" {   // удаление связки — откатить перелив целевых сумм
            let id = Int(m[1]) ?? -1
            if let mv = try db.rows("SELECT from_id, to_id, amount FROM target_moves WHERE id = ?", [id]).first {
                let amt = num(mv["amount"])   // в €
                let rate = (try? eurUsdRate(db)) ?? 1.08
                if let f = numOpt(mv["from_id"]) { let fid = Int(f); let c = scalarStr(db, "SELECT currency FROM target_items WHERE id = ?", [fid]) ?? "€"; try db.run("UPDATE target_items SET value = COALESCE(value,0) + ? WHERE id = ?", [c == "$" ? amt * rate : amt, fid]) }
                if let t = numOpt(mv["to_id"]) { let tid = Int(t); let c = scalarStr(db, "SELECT currency FROM target_items WHERE id = ?", [tid]) ?? "€"; try db.run("UPDATE target_items SET value = COALESCE(value,0) - ? WHERE id = ?", [c == "$" ? amt * rate : amt, tid]) }
            }
            try db.run("DELETE FROM target_moves WHERE id = ?", [id]); return (ok(), 200)
        }
        if let m = match(path, "^/api/fin/(accounts|classes|steps|obligations|items|tx|debts|income|budget|tgt|move)(?:/([0-9]+))?$") {
            let entity = m[1], idStr = m[2], table = finTable[entity] ?? entity
            if method == "POST" && idStr.isEmpty { try finAdd(db, entity, body); return (ok(201), 201) }
            if method == "PATCH" && !idStr.isEmpty { try patchCols(db, table, Int(idStr) ?? -1, finCols[entity] ?? [], body); return (ok(), 200) }
            if method == "DELETE" && !idStr.isEmpty { try db.run("DELETE FROM \(table) WHERE id = ?", [Int(idStr) ?? -1]); return (ok(), 200) }
        }
        if let m = match(path, "^/api/fin/items/([0-9]+)/move$"), method == "POST" {
            do { try finMoveItem(db, id: Int(m[1]) ?? -1, parent: numOpt(body["parent_id"]).map { Int($0) }); return (ok(), 200) } catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/fin/items/([0-9]+)/reorder$"), method == "POST" {
            guard let ref = numOpt(body["ref_id"]).map({ Int($0) }) else { return (try json(["error": "ref_id"]), 400) }
            do { try finReorderItem(db, id: Int(m[1]) ?? -1, refId: ref, pos: (body["where"] as? String) == "before" ? "before" : "after"); return (ok(), 200) } catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/fin/tgt/([0-9]+)/move$"), method == "POST" {
            do { try finMoveItem(db, id: Int(m[1]) ?? -1, parent: numOpt(body["parent_id"]).map { Int($0) }, "target_items"); return (ok(), 200) } catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/fin/tgt/([0-9]+)/reorder$"), method == "POST" {
            guard let ref = numOpt(body["ref_id"]).map({ Int($0) }) else { return (try json(["error": "ref_id"]), 400) }
            do { try finReorderItem(db, id: Int(m[1]) ?? -1, refId: ref, pos: (body["where"] as? String) == "before" ? "before" : "after", "target_items"); return (ok(), 200) } catch { return (errJson(error), 400) }
        }
        if let m = match(path, "^/api/fin/obligations/([0-9]+)/pay$"), method == "POST" {
            return (try json(try payObligation(db, id: Int(m[1]) ?? -1)), 200)
        }
        if let m = match(path, "^/api/fin/steps/([0-9]+)/task$"), method == "POST" {
            do { return (try json(try stepToTask(db, stepId: Int(m[1]) ?? -1)), 201) } catch { return (errJson(error), 400) }
        }
        if method == "POST", path == "/api/fin/fire" {
            for k in ["fire_target", "fire_return_pct", "fire_monthly_savings"] where body[k] != nil { try setSetting(db, k, body[k]) }
            return (ok(), 200)
        }
        if method == "POST", path == "/api/fin/forecasts" {
            guard let st = name(body, "statement") else { return (try json(["error": "statement required"]), 400) }
            try db.run("INSERT INTO forecasts(statement, confidence, due_date) VALUES(?,?,?)", [st, intval(body["confidence"]), body["due_date"] ?? NSNull()])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/fin/forecasts/([0-9]+)/resolve$"), method == "POST" {
            let outcome = (body["outcome"] as? Bool == true || intval(body["outcome"]) != 0) ? 1 : 0
            try db.run("UPDATE forecasts SET outcome = ?, resolved_at = datetime('now','localtime') WHERE id = ?", [outcome, Int(m[1]) ?? -1])
            return (ok(), 200)
        }
        if let m = match(path, "^/api/fin/forecasts/([0-9]+)$"), method == "DELETE" {
            try db.run("DELETE FROM forecasts WHERE id = ?", [Int(m[1]) ?? -1]); return (ok(), 200)
        }
        if method == "POST", path == "/api/fin/properties" {
            guard let nm = name(body) else { return (nameErr(), 400) }
            try db.run("INSERT INTO properties(name, category, note) VALUES(?,?,?)", [nm, body["category"] as? String ?? "прочее", body["note"] as? String ?? ""])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/fin/properties/([0-9]+)/rules$"), method == "POST" {
            let pid = Int(m[1]) ?? -1
            guard let rn = name(body) else { return (nameErr(), 400) }
            guard let pname = (try db.rows("SELECT name FROM properties WHERE id = ?", [pid]).first?["name"]) as? String else {
                return (try json(["error": "объект не найден"]), 400)
            }
            // регламент имущества = обязательство, привязанное к объекту (порт fin.addRule)
            try db.run("INSERT INTO obligations(name, amount, currency, period, next_date, remind_days, kind, property_id) VALUES(?,?,?,?,?,?,'liability',?)",
                ["\(pname): \(rn)", num(body["amount"]), body["currency"] as? String ?? "€",
                 body["period"] as? String ?? "yearly", body["next_date"] ?? NSNull(),
                 intval(body["remind_days"] ?? 7), pid])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/fin/properties/([0-9]+)$") {
            let id = Int(m[1]) ?? -1
            if method == "PATCH" { try patchCols(db, "properties", id, ["name", "category", "note"], body); return (ok(), 200) }
            if method == "DELETE" { try db.run("DELETE FROM properties WHERE id = ?", [id]); return (ok(), 200) }
        }
        if method == "POST", path == "/api/fin/macro" {
            try db.run("INSERT INTO macro_notes(phase, thesis) VALUES(?,?)", [body["phase"] as? String ?? "", body["thesis"] as? String ?? ""])
            return (ok(201), 201)
        }
        if let m = match(path, "^/api/fin/macro/([0-9]+)$"), method == "DELETE" {
            try db.run("DELETE FROM macro_notes WHERE id = ?", [Int(m[1]) ?? -1]); return (ok(), 200)
        }
        if let m = match(path, "^/api/rates/([^/]+)$"), method == "PATCH" {
            let sym = m[1].removingPercentEncoding ?? m[1]
            try db.run("UPDATE rates SET price = ?, change_pct = NULL, updated_at = datetime('now','localtime') WHERE symbol = ?", [num(body["price"]), sym])
            return (try json(try db.rows("SELECT * FROM rates WHERE symbol = ?", [sym]).first ?? [:]), 200)
        }
        return nil
    }

    static func finAdd(_ db: Database, _ entity: String, _ b: [String: Any]) throws {
        switch entity {
        case "accounts":
            try db.run("INSERT INTO accounts(name, type, currency, balance) VALUES(?,?,?,?)",
                [b["name"] as? String ?? "", b["type"] as? String ?? "bank", b["currency"] as? String ?? "€", num(b["balance"])])
        case "classes":
            let ord = nextOrd(db, "SELECT COALESCE(MAX(ord),0)+1 AS o FROM portfolio_classes")
            try db.run("INSERT INTO portfolio_classes(name, value, target_pct, ord) VALUES(?,?,?,?)",
                [b["name"] as? String ?? "", num(b["value"]), num(b["target_pct"]), ord])
        case "steps":
            try db.run("INSERT INTO steps(kind, title, amount, planned_date, condition, note) VALUES(?,?,?,?,?,?)",
                [b["kind"] as? String ?? "buy", b["title"] as? String ?? "", b["amount"] ?? NSNull(), b["planned_date"] ?? NSNull(), b["condition"] as? String ?? "", b["note"] as? String ?? ""])
        case "obligations":
            try db.run("INSERT INTO obligations(name, amount, currency, period, next_date, remind_days, kind, note, due_time) VALUES(?,?,?,?,?,?,?,?,?)",
                [b["name"] as? String ?? "", num(b["amount"]), b["currency"] as? String ?? "€", b["period"] as? String ?? "monthly",
                 b["next_date"] ?? NSNull(), intval(b["remind_days"] ?? 5), b["kind"] as? String ?? "liability", b["note"] as? String ?? "", b["due_time"] ?? NSNull()])
        case "items":
            let parent = numOpt(b["parent_id"]).map { Int($0) }
            let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM portfolio_items WHERE parent_id IS ?", [parent]).first?["o"]))
            try db.run("INSERT INTO portfolio_items(parent_id, ord, name, kind, buy_value, value, target_value, currency) VALUES(?,?,?,?,?,?,?,?)",
                [parent, ord, b["name"] as? String ?? "", b["kind"] as? String ?? "asset", b["buy_value"] ?? NSNull(), b["value"] ?? NSNull(), b["target_value"] ?? NSNull(), b["currency"] as? String ?? "€"])
        case "tx":
            try db.run("INSERT INTO transactions(date, amount, currency, direction, category, note, source) VALUES(?,?,?,?,?,?,?)",
                [b["date"] as? String ?? localToday(), abs(num(b["amount"])), b["currency"] as? String ?? "€",
                 b["direction"] as? String ?? "expense", name(b, "category") ?? "прочее", b["note"] as? String ?? "", b["source"] as? String ?? "manual"])
        case "debts":
            try db.run("INSERT INTO debts(name, amount, currency, direction, due_date, note) VALUES(?,?,?,?,?,?)",
                [b["name"] as? String ?? "", num(b["amount"]), b["currency"] as? String ?? "€", b["direction"] as? String ?? "owed_to_me", b["due_date"] ?? NSNull(), b["note"] as? String ?? ""])
        case "income":
            try db.run("INSERT INTO passive_income(name, amount, currency, period, next_date, note, principal, rate, rate_period, asset_type) VALUES(?,?,?,?,?,?,?,?,?,?)",
                [b["name"] as? String ?? "", num(b["amount"]), b["currency"] as? String ?? "€", b["period"] as? String ?? "monthly", b["next_date"] ?? NSNull(), b["note"] as? String ?? "",
                 num(b["principal"]), num(b["rate"]), b["rate_period"] as? String ?? "yearly", b["asset_type"] as? String ?? ""])
        case "budget":
            let ord = nextOrd(db, "SELECT COALESCE(MAX(ord),0)+1 AS o FROM budget_items")
            try db.run("INSERT INTO budget_items(name, amount, currency, direction, ord, month) VALUES(?,?,?,?,?,?)",
                [b["name"] as? String ?? "", num(b["amount"]), b["currency"] as? String ?? "€", b["direction"] as? String ?? "expense", ord, b["month"] ?? NSNull()])
        case "tgt":
            let parent = numOpt(b["parent_id"]).map { Int($0) }
            let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM target_items WHERE parent_id IS ?", [parent]).first?["o"]))
            try db.run("INSERT INTO target_items(parent_id, ord, name, kind, value, currency, asset_type) VALUES(?,?,?,?,?,?,?)",
                [parent, ord, b["name"] as? String ?? "", b["kind"] as? String ?? "asset", b["value"] ?? NSNull(), b["currency"] as? String ?? "€", b["asset_type"] ?? NSNull()])
        case "move":
            let mvFrom = numOpt(b["from_id"]).map { Int($0) }, mvTo = numOpt(b["to_id"]).map { Int($0) }
            let mvRate = (try? eurUsdRate(db)) ?? 1.08
            let mvFromCur = mvFrom.flatMap { scalarStr(db, "SELECT currency FROM target_items WHERE id = ?", [$0]) } ?? "€"
            let mvInput = num(b["amount"])   // сумму вводят в валюте ИСТОЧНИКА (переношу доллары — ввожу доллары)
            let mvAmt = mvFromCur == "$" ? mvInput / mvRate : mvInput   // храним якорь в €
            try db.run("INSERT INTO target_moves(from_id, to_id, amount) VALUES(?,?,?)", [mvFrom ?? NSNull(), mvTo ?? NSNull(), mvAmt])
            // списываем ровно введённую сумму из источника, зачисляем эквивалент получателю — каждый в своей валюте
            if let f = mvFrom { try db.run("UPDATE target_items SET value = COALESCE(value,0) - ? WHERE id = ?", [mvFromCur == "$" ? mvAmt * mvRate : mvAmt, f]) }
            if let t = mvTo { let c = scalarStr(db, "SELECT currency FROM target_items WHERE id = ?", [t]) ?? "€"; try db.run("UPDATE target_items SET value = COALESCE(value,0) + ? WHERE id = ?", [c == "$" ? mvAmt * mvRate : mvAmt, t]) }
        default: break
        }
    }
    static func finMoveItem(_ db: Database, id: Int, parent: Int?, _ table: String = "portfolio_items") throws {
        if let p = parent {
            if p == id { throw Unsupported(path: "self") }
            let desc = try db.rows("WITH RECURSIVE r(x) AS (SELECT id FROM \(table) WHERE parent_id = ? UNION SELECT n.id FROM \(table) n JOIN r ON n.parent_id = r.x) SELECT 1 FROM r WHERE x = ? LIMIT 1", [id, p])
            if !desc.isEmpty { throw Unsupported(path: "descendant") }
        }
        let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM \(table) WHERE parent_id IS ?", [parent]).first?["o"]))
        try db.run("UPDATE \(table) SET parent_id = ?, ord = ? WHERE id = ?", [parent, ord, id])
    }
    static func finReorderItem(_ db: Database, id: Int, refId: Int, pos: String, _ table: String = "portfolio_items") throws {
        if id == refId { throw Unsupported(path: "self") }
        guard let ref = try db.rows("SELECT id, parent_id FROM \(table) WHERE id = ?", [refId]).first else { throw Unsupported(path: "ref not found") }
        let rp = numOpt(ref["parent_id"]).map { Int($0) }
        if rp == id { throw Unsupported(path: "descendant") }
        if let rpp = rp {
            let desc = try db.rows("WITH RECURSIVE r(x) AS (SELECT id FROM \(table) WHERE parent_id = ? UNION SELECT n.id FROM \(table) n JOIN r ON n.parent_id = r.x) SELECT 1 FROM r WHERE x = ? LIMIT 1", [id, rpp])
            if !desc.isEmpty { throw Unsupported(path: "descendant") }
        }
        var siblings = try db.rows("SELECT id FROM \(table) WHERE parent_id IS ? ORDER BY ord, id", [rp]).compactMap { $0["id"] as? Int }.filter { $0 != id }
        if let idx = siblings.firstIndex(of: refId) { siblings.insert(id, at: idx + (pos == "after" ? 1 : 0)) } else { siblings.append(id) }
        try db.run("UPDATE \(table) SET parent_id = ? WHERE id = ?", [rp, id])
        for (i, sid) in siblings.enumerated() { try db.run("UPDATE \(table) SET ord = ? WHERE id = ?", [i + 1, sid]) }
    }
    static func payObligation(_ db: Database, id: Int) throws -> [String: Any] {
        guard let o = try db.rows("SELECT * FROM obligations WHERE id = ?", [id]).first, let nd = o["next_date"] as? String else {
            return try db.rows("SELECT * FROM obligations WHERE id = ?", [id]).first ?? [:]
        }
        let period = o["period"] as? String
        let next: Any
        if period == "monthly" { next = addMonths(nd, 1) }
        else if period == "yearly" { next = addMonths(nd, 12) }
        else { next = NSNull() }
        try db.run("UPDATE obligations SET next_date = ? WHERE id = ?", [next, id])
        return try db.rows("SELECT * FROM obligations WHERE id = ?", [id]).first ?? [:]
    }
    static func stepToTask(_ db: Database, stepId: Int) throws -> Data {
        guard let s = try db.rows("SELECT * FROM steps WHERE id = ?", [stepId]).first else { throw Unsupported(path: "step not found") }
        if let taskId = numOpt(s["task_id"]).map({ Int($0) }), let existing = try getNode(db, taskId) {
            var e = existing; e["already"] = true; return try json(e)
        }
        let fin = try db.rows("SELECT id FROM nodes WHERE is_category = 1 AND title = 'Финансы' AND parent_id IS NULL").first
        let KIND = ["buy": "Купить", "sell": "Продать", "transfer": "Перевести"]
        let kind = s["kind"] as? String ?? ""
        let node = try addChild(db, parentId: fin.map { intval($0["id"]) }, title: "\(KIND[kind] ?? kind): \(s["title"] as? String ?? "")") ?? [:]
        let noteParts = ["из плана шагов портфеля", numOpt(s["amount"]) != nil ? "сумма: \(intval(s["amount"]))" : "", (s["condition"] as? String).flatMap { $0.isEmpty ? nil : "условие: \($0)" } ?? ""].filter { !$0.isEmpty }
        let updated = try updateNode(db, id: intval(node["id"]), fields: ["kind": "task", "due_date": s["planned_date"] ?? NSNull(), "note": noteParts.joined(separator: " · ")]) ?? [:]
        try db.run("UPDATE steps SET task_id = ? WHERE id = ?", [intval(node["id"]), stepId])
        return try json(updated)
    }

    // Карточка-инспектор узла: сам узел + подсказка типа + существующие связи.
    // (умные подсказки-связи по токенам и контекст ветки — добавлю отдельным срезом)
    static func suggest(_ db: Database, id: Int) throws -> Data {
        guard let t = try getNode(db, id) else { return try json(NSNull()) }
        let title = t["title"] as? String ?? "", note = t["note"] as? String ?? ""
        // семья = сам + предки + потомки
        var family: Set<Int> = [id]
        var cur: Int? = id
        while let c = cur, let n = try getNode(db, c), let p = numOpt(n["parent_id"]).map({ Int($0) }) { family.insert(p); cur = p }
        for d in try db.rows("WITH RECURSIVE r(x) AS (SELECT id FROM nodes WHERE parent_id = ? UNION SELECT n.id FROM nodes n JOIN r ON n.parent_id = r.x) SELECT x FROM r", [id]) { family.insert(intval(d["x"])) }
        let linked = Set(try db.rows("SELECT from_id AS x FROM links WHERE to_id = ? UNION SELECT to_id FROM links WHERE from_id = ?", [id, id]).map { intval($0["x"]) })
        var dism: Set<Int> = []
        for r in try db.rows("SELECT a, b FROM dismissed") { let a = intval(r["a"]), b = intval(r["b"]); if a == id { dism.insert(b) } else if b == id { dism.insert(a) } }
        let myToks = tokens(title + " " + note)
        var candidates: [[String: Any]] = []
        if !myToks.isEmpty {
            let q = myToks.map { "\"\($0.replacingOccurrences(of: "\"", with: ""))\"" }.joined(separator: " OR ")
            for c in try db.rows("SELECT n.*, bm25(node_fts) AS rank FROM node_fts JOIN nodes n ON n.id = node_fts.rowid WHERE node_fts MATCH ? ORDER BY rank LIMIT 20", [q]) {
                let cid = intval(c["id"])
                if family.contains(cid) || linked.contains(cid) || dism.contains(cid) { continue }
                let common = tokens((c["title"] as? String ?? "") + " " + (c["note"] as? String ?? "")).filter { myToks.contains($0) }
                let reason = "совпадение: " + common.prefix(4).joined(separator: ", ")
                if reason.count > 12 { candidates.append(["node": c, "reason": reason, "kind": "mention"]) }
            }
        }
        if let due = t["due_date"] as? String, !due.isEmpty {
            for c in try db.rows("SELECT * FROM nodes WHERE due_date IS NOT NULL AND id != ? AND abs(julianday(due_date) - julianday(?)) <= 60", [id, due]) {
                let cid = intval(c["id"])
                if family.contains(cid) || linked.contains(cid) || dism.contains(cid) { continue }
                candidates.append(["node": c, "reason": "дата рядом: \(c["due_date"] as? String ?? "")", "kind": "time"])
            }
        }
        var seen: Set<Int> = []; var links: [[String: Any]] = []
        for c in candidates { let nid = intval((c["node"] as? [String: Any])?["id"]); if seen.insert(nid).inserted { links.append(c) }; if links.count >= 8 { break } }
        // контекст ветки
        var branchRoot = t
        while let p = numOpt(branchRoot["parent_id"]).map({ Int($0) }), let pp = try getNode(db, p), intval(pp["is_category"]) == 0 { branchRoot = pp }
        var branchIds: Set<Int> = [intval(branchRoot["id"])]
        for d in try db.rows("WITH RECURSIVE r(x) AS (SELECT id FROM nodes WHERE parent_id = ? UNION SELECT n.id FROM nodes n JOIN r ON n.parent_id = r.x) SELECT x FROM r", [intval(branchRoot["id"])]) { branchIds.insert(intval(d["x"])) }
        branchIds.remove(id)
        func inBranch(_ rows: [[String: Any]]) -> [[String: Any]] { rows.filter { branchIds.contains(intval($0["id"])) } }
        let principles = inBranch(try db.rows("SELECT * FROM nodes WHERE kind = 'principle'"))
        let decisions = inBranch(try db.rows("SELECT * FROM nodes WHERE kind = 'decision' AND status = 'open'"))
        var payments: [[String: Any]] = []
        if let due = t["due_date"] as? String, !due.isEmpty {
            payments = try db.rows("SELECT * FROM obligations WHERE next_date IS NOT NULL AND abs(julianday(next_date) - julianday(?)) <= 60 ORDER BY next_date", [due])
        }
        let confirmed = try db.rows("SELECT l.id AS link_id, l.type, l.from_id, l.to_id, n.title, n.status, n.kind AS nkind FROM links l JOIN nodes n ON n.id = CASE WHEN l.from_id = ? THEN l.to_id ELSE l.from_id END WHERE l.from_id = ? OR l.to_id = ?", [id, id, id])
        let hasKind = !(t["kind"] is NSNull) && t["kind"] != nil
        let hasDue = !(t["due_date"] is NSNull) && (t["due_date"] as? String)?.isEmpty == false
        let result: [String: Any] = [
            "node": t,
            "kind": hasKind ? NSNull() : (suggestKind(title) ?? NSNull()),
            "date": hasDue ? NSNull() : (suggestDate(title).map { $0 as Any } ?? NSNull()),
            "links": links, "context": ["principles": principles, "decisions": decisions, "payments": payments],
            "confirmed": confirmed,
        ]
        return try json(result)
    }
    private static let MONTHS: [(String, Int)] = [("январ", 1), ("феврал", 2), ("март", 3), ("апрел", 4), ("ма[йя]", 5), ("июн", 6),
        ("июл", 7), ("август", 8), ("сентябр", 9), ("октябр", 10), ("ноябр", 11), ("декабр", 12)]
    private static func suggestDate(_ title: String) -> String? {
        let t = title.lowercased()
        if let r = t.range(of: "до\\s+(20[0-9][0-9])", options: .regularExpression) {
            let yr = String(t[r]).components(separatedBy: CharacterSet.decimalDigits.inverted).filter { !$0.isEmpty }.last
            if let y = yr.flatMap({ Int($0) }) { return "\(y - 1)-12-31" }
        }
        let now = Date(); let cal = Calendar.current
        let curY = cal.component(.year, from: now), curM = cal.component(.month, from: now)
        for (pat, m) in MONTHS where regexTest(t, "(?:^|[^а-яёa-z])(?:\(pat))") {
            let y = m < curM ? curY + 1 : curY
            var c = Calendar(identifier: .gregorian); c.timeZone = TimeZone(identifier: "UTC")!
            let last = c.range(of: .day, in: .month, for: c.date(from: DateComponents(year: y, month: m, day: 1))!)!.count
            return String(format: "%04d-%02d-%02d", y, m, last)
        }
        return nil
    }

    private static func regexTest(_ s: String, _ pattern: String) -> Bool {
        guard let re = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else { return false }
        return re.firstMatch(in: s, range: NSRange(s.startIndex..., in: s)) != nil
    }
    // Авто-тип по тексту — порт core.suggestKind.
    private static func suggestKind(_ title: String) -> String? {
        let t = title.trimmingCharacters(in: .whitespacesAndNewlines)
        if regexTest(t, "(боюсь|страшно|тревож|переживаю|волнуюсь|а вдруг|а если)") { return "worry" }
        if regexTest(t, "^(стоит ли|как мы|что лучше|или\\b)") { return "decision" }
        if regexTest(t, "\\?\\s*$") { return "question" }
        let letters = t.filter { $0.isLetter }.count
        let upper = t.filter { $0.isUppercase }.count
        if letters >= 5 && Double(upper) / Double(letters) > 0.7 { return "principle" }
        if regexTest(t, "^(понять|продать|купить|найти|находим|написать|посмотреть|посмотрим|использовать|сделать|назначить|подумать|сформулирую|формулирую|изучить|закрыть|общаемся|ведем|ведём|завести|положить|оплатить|проверить|узнать|записаться|выбрать|решить)") { return "task" }
        return nil
    }

    // ----- Узлы целей (порт core.js: insert/update/toggle/reorder/move/delete) -----
    private static let HOMO: [Character: Character] = ["а": "a", "е": "e", "о": "o", "с": "c", "р": "p",
        "х": "x", "у": "y", "к": "k", "в": "b", "м": "m", "т": "t"]
    static func norm(_ s: String) -> String { String(s.lowercased().map { HOMO[$0] ?? $0 }) }
    private static let PATCHABLE = ["title", "note", "kind", "status", "priority", "due_date", "due_time", "answer", "repeat"]

    static func getNode(_ db: Database, _ id: Int) throws -> [String: Any]? {
        try db.rows("SELECT * FROM nodes WHERE id = ?", [id]).first
    }

    // Каркас категорий для чистой установки (iOS / свежий Mac) — порт db.seed().
    static func seedIfEmpty(_ db: Database) throws {
        try db.ensureSchema()   // на iOS/чистом Mac таблиц ещё нет — создаём перед сидом
        if ((try db.rows("SELECT count(*) AS c FROM nodes").first?["c"]) as? Int ?? 0) == 0 {
            func cat(_ parent: Int?, _ title: String) throws -> Int { try insertNode(db, parentId: parent, title: title, note: "", isCategory: 1) }
            _ = try cat(nil, "📥 Инбокс")
            let fin = try cat(nil, "Финансы"); for c in ["Налоги", "Платежи", "Балансы", "Траты", "Активы", "Пассивы"] { _ = try cat(fin, c) }
            let leg = try cat(nil, "Легализация"); _ = try cat(leg, "ВНЖ")
            let work = try cat(nil, "Работа"); for c in ["Рост", "Проекты"] { _ = try cat(work, c) }
            let life = try cat(nil, "Жизнь"); for c in ["Семья", "Развитие", "Здоровье", "Отдых"] { _ = try cat(life, c) }
            let hist = try cat(nil, "История и расчёты"); for c in ["Налоговые расчёты", "История"] { _ = try cat(hist, c) }
            let fears = try cat(nil, "Страхи / Вопросы"); let trev = try cat(fears, "Тревоги")
            for c in ["Налоги", "Покупки", "ВНЖ", "Балансы", "Брокеры", "Семья", "Работа", "Принятые"] { _ = try cat(trev, c) }
            _ = try cat(nil, "Глобальные цели")
        }
        // как server.js на старте: каркас портфеля, строки курсов, ⚡ Энергия жизни
        try ensurePortfolio(db)
        try ensureRates(db)
        try ensureEnergy(db)
    }

    // Техника-практика, создаваемая один раз (флаг в settings). Через try? — открытие базы не падает,
    // если таблицы ещё нет. Имя-проверка не плодит дубли при синхроне Mac↔iPhone.
    private static func seedTechniqueOnce(_ db: Database, flag: String, name: String, steps: [String], note: String) {
        let stepsJson = String(data: (try? JSONSerialization.data(withJSONObject: steps)) ?? Data("[]".utf8), encoding: .utf8) ?? "[]"
        if let row = (try? db.rows("SELECT id, steps FROM practices WHERE name LIKE ? AND name NOT LIKE '%(пример)%'", [name + "%"]))?.first {
            // практика уже есть: если шаги пустые (создана раньше без них) — дозаполнить
            let s = (row["steps"] as? String) ?? ""
            if s.isEmpty || s == "[]" { _ = try? db.run("UPDATE practices SET steps = ? WHERE id = ?", [stepsJson, intval(row["id"])]) }
        } else if ((try? db.rows("SELECT value FROM settings WHERE key = ?", [flag]))?.first?["value"]) as? String != "1" {
            let ord = nextOrd(db, "SELECT COALESCE(MAX(ord),0)+1 AS o FROM practices")
            _ = try? db.run("INSERT INTO practices(name, kind, days, time, steps, note, ord) VALUES(?,?,?,?,?,?,?)",
                [name, "technique", "", NSNull(), stepsJson, note, ord])
        }
        try? setSetting(db, flag, "1")
    }

    // Техника «Тестирование мыслей» (когнитивная реструктуризация, КПТ) — создаётся один раз.
    static func ensureThoughtTesting(_ db: Database) {
        seedTechniqueOnce(db, flag: "tt_v1", name: "Тестирование мыслей", steps: [
            "🧠 Мысли. Какая у меня есть мысль о себе, людях или мире? (насколько верю в неё, 1–100?)",
            "❤️ Чувства. Что я чувствую в ответ на эту мысль? (сила чувств, 1–100?)",
            "➕ Аргументы «За». Что говорит в пользу полезности и/или реалистичности этой мысли?",
            "➖ Аргументы «Против». Что говорит о её вредности и/или нереалистичности? И что опровергает аргументы «за»?",
            "🔄 Реалистичные и полезные мысли. Как может быть по-другому? Какие более реалистичные и полезные мысли можно выбрать теперь — под мои цели?",
            "✅ Результат. Насколько теперь верю в изначальную мысль (1–100)? Какой силы первые эмоции?",
        ], note: "когнитивная реструктуризация: проверяю мысль на реалистичность и пользу, выбираю более полезную")
    }

    // Техника «Дневник мыслей» (CBT thought record) — журнал случаев таблицей, создаётся один раз.
    static func ensureThoughtDiary(_ db: Database) {
        seedTechniqueOnce(db, flag: "td_v1", name: "Дневник мыслей", steps: [
            "Ситуация (что произошло / происходит?)",
            "«Мысли» (что думаю о себе, ситуации, мире, людях?)",
            "Эмоции 1–100 (что чувствую и насколько сильно? напр. «Беспокойство (90)»)",
            "Поведение (что хочу делать? что делаю?)",
        ], note: "ловлю случай: ситуация → мысли → эмоции (1–100) → поведение. Журнал копится таблицей для пересмотра")
    }

    // Техника «Дневник Опыта» — разбор случая, где себя остановил.
    static func ensureExperienceDiary(_ db: Database) {
        seedTechniqueOnce(db, flag: "exp_v1", name: "Дневник Опыта", steps: [
            "Ситуация. Что было? Что сделал / не сделал?",
            "Чувства. Что я там чувствовал? (1–100)",
            "Мысли. Какими мыслями себя остановил?",
            "Принятие и разрешение. Есть причины — какие?",
            "Планирование. Как хочу поступить в следующий раз? Как думать, говорить, действовать?",
        ], note: "разбираю случай, где себя остановил: ситуация → чувства → мысли → принятие → план на будущее")
    }

    // Техника «Дневник Побед» — закрепляю успех и новые выводы.
    static func ensureWinsDiary(_ db: Database) {
        seedTechniqueOnce(db, flag: "win_v1", name: "Дневник Побед", steps: [
            "Ситуация. Какая ситуация? Что я сделал и как?",
            "Что в результате? Какие реакции, факты?",
            "Что чувствовал? (1–100)",
            "Какие новые выводы выбираю сделать о себе, людях, мире, возможностях, силе, безопасности — и о чём напоминать себе в следующих подобных ситуациях?",
        ], note: "закрепляю успех: ситуация → результат → чувства → новые выводы о себе и мире")
    }

    // Категории практик по умолчанию для известных техник — один раз (psy_cat_v1),
    // только если категория ещё не задана. Дальше пользователь меняет вручную.
    static func ensurePracticeCategories(_ db: Database) {
        if ((try? db.rows("SELECT value FROM settings WHERE key = 'psy_cat_v1'"))?.first?["value"]) as? String == "1" { return }
        let defaults: [(String, String)] = [
            ("Позитивное намерение", "убеждения"), ("Тестирование мыслей", "убеждения"),
            ("Дневник мыслей", "опыт"), ("Дневник Опыта", "опыт"),
            ("Дневник Побед", "мотивация"), ("Дневник настройки", "сценарии"),
        ]
        for (name, cat) in defaults {
            try? db.run("UPDATE practices SET category = ? WHERE name LIKE ? AND (category IS NULL OR category = '') AND name NOT LIKE '%(пример)%'", [cat, name + "%"])
        }
        try? setSetting(db, "psy_cat_v1", "1")
    }

    // Свести дубли практик (одинаковое имя, появляются после синхрона Mac↔iPhone с разными id).
    // Оставляем min(id), переносим всю историю отметок и заполненные поля; лишние удаляем —
    // триггер ставит tombstone, и удаление расходится на другие устройства. Идемпотентно (нет дублей → no-op).
    static func dedupePractices(_ db: Database) {
        guard let groups = try? db.rows("SELECT name, COUNT(*) AS c, MIN(id) AS keep FROM practices GROUP BY name HAVING c > 1") else { return }
        for g in groups {
            let keep = intval(g["keep"])
            guard let name = g["name"] as? String,
                  let dups = try? db.rows("SELECT * FROM practices WHERE name = ? AND id <> ?", [name, keep]) else { continue }
            for d in dups {
                let did = intval(d["id"])
                try? db.run("UPDATE practice_log SET practice_id = ? WHERE practice_id = ?", [keep, did])   // сохранить историю отметок
                for col in ["steps", "note", "time", "days", "category"] {   // подтянуть заполненные поля, если у оставляемой пусто
                    if let v = d[col] as? String, !v.isEmpty, v != "[]" {
                        try? db.run("UPDATE practices SET \(col) = ? WHERE id = ? AND (\(col) IS NULL OR \(col) = '' OR \(col) = '[]')", [v, keep])
                    }
                }
                if intval(d["continuous"]) == 1 { try? db.run("UPDATE practices SET continuous = 1 WHERE id = ?", [keep]) }
                try? db.run("DELETE FROM practices WHERE id = ?", [did])   // tombstone → удаление дубля уедет на телефон
            }
        }
    }

    // Дефолтные расходы/доходы (списком): первичное заполнение из фактических транзакций месяца-базы 2026-06,
    // сгруппированных по направлению+категории. Один раз (флаг) и только если список пуст — ручные не перетираем.
    static func seedBudgetItems(_ db: Database) {
        if ((try? db.rows("SELECT value FROM settings WHERE key = 'budget_seed_v2'"))?.first?["value"]) as? String == "1" { return }
        let cnt = intval((try? db.rows("SELECT COUNT(*) AS c FROM budget_items"))?.first?["c"])
        if cnt == 0 {
            _ = try? db.run("""
                INSERT INTO budget_items(direction, name, amount, currency, month)
                SELECT direction, category, ROUND(SUM(amount), 2), MAX(currency),
                       CASE WHEN direction = 'income' THEN '2026-06' ELSE NULL END
                FROM transactions WHERE substr(date,1,7) = '2026-06'
                GROUP BY direction, category
                """)
        }
        _ = try? setSetting(db, "budget_seed_v2", "1")
    }

    // Целевой портфель: первичное заполнение структурой фактического (один раз, флаг).
    // Копируем дерево portfolio_items → target_items, сохраняя иерархию (маппинг старый id → новый).
    // Дальше целевой правится независимо; суммы — стартовые, пользователь меняет.
    static func initTargetFromFact(_ db: Database) {
        if ((try? db.rows("SELECT value FROM settings WHERE key = 'target_seed_v1'"))?.first?["value"]) as? String == "1" { return }
        if intval((try? db.rows("SELECT COUNT(*) AS c FROM target_items"))?.first?["c"]) == 0,
           let rows = try? db.rows("SELECT * FROM portfolio_items ORDER BY parent_id NULLS FIRST, ord, id") {
            var map: [Int: Int] = [:]
            // проход 1: вставляем все узлы БЕЗ родителя, собираем маппинг старый→новый id.
            // rate_symbol/qty НЕ копируем: в целевом (плановом) автоцена перебила бы плановую сумму.
            // value — стартовая плановая (для авто-активов — текущая рыночная как ориентир).
            for r in rows {
                if let newId = try? db.run("INSERT INTO target_items(parent_id, ord, name, kind, value, currency, asset_type, region, note) VALUES(NULL,?,?,?,?,?,?,?,?)",
                    [intval(r["ord"]), r["name"] ?? "", r["kind"] ?? "asset",
                     r["value"] ?? NSNull(), r["currency"] ?? "€", r["asset_type"] ?? NSNull(), r["region"] ?? NSNull(), r["note"] ?? NSNull()]) {
                    map[intval(r["id"])] = newId
                }
            }
            // проход 2: проставляем parent_id по маппингу — не зависит от порядка вставки (id могли перемешаться
            // после синхронов/дедупа, и ORDER BY parent_id не гарантирует «родитель раньше ребёнка»)
            for r in rows {
                if let op = numOpt(r["parent_id"]).map({ Int($0) }), let np = map[op], let nid = map[intval(r["id"])] {
                    _ = try? db.run("UPDATE target_items SET parent_id = ? WHERE id = ?", [np, nid])
                }
            }
        }
        _ = try? setSetting(db, "target_seed_v1", "1")
    }

    // Свести дубли категорий/позиций дерева портфеля (одинаковый parent + имя, но разные id — расходятся после
    // синхрона Mac↔iPhone). Имя сравниваем без учёта регистра и крайних пробелов. Оставляем min(id); заполненные
    // поля, детей и связки переносим на keep, лишние удаляем. Цикл: слияние уровня может открыть дубли ниже.
    static func dedupeTreeItems(_ db: Database, _ table: String, _ movesTable: String?) {
        let mergeCols = ["value", "buy_value", "target_value", "asset_type", "region", "note", "rate_symbol", "qty"]
        for _ in 0..<30 {
            guard let groups = try? db.rows("SELECT MIN(id) AS keep, COUNT(*) AS c FROM \(table) GROUP BY IFNULL(parent_id,-1), LOWER(TRIM(name)) HAVING c > 1"),
                  !groups.isEmpty else { return }
            for g in groups {
                let keep = intval(g["keep"])
                guard let kp = (try? db.rows("SELECT parent_id, name FROM \(table) WHERE id=?", [keep]))?.first,
                      let dups = try? db.rows("SELECT * FROM \(table) WHERE IFNULL(parent_id,-1)=IFNULL(?,-1) AND LOWER(TRIM(name))=LOWER(TRIM(?)) AND id<>?",
                        [kp["parent_id"] ?? NSNull(), kp["name"] as? String ?? "", keep]) else { continue }
                for d in dups {
                    let did = intval(d["id"])
                    for c in mergeCols {   // подтянуть заполненное с дубля, если у keep пусто (не теряем суммы/тип/регион)
                        if let v = d[c], !(v is NSNull), !((v as? String)?.isEmpty ?? false) {
                            try? db.run("UPDATE \(table) SET \(c)=? WHERE id=? AND (\(c) IS NULL OR \(c)='')", [v, keep])
                        }
                    }
                    try? db.run("UPDATE \(table) SET parent_id=? WHERE parent_id=?", [keep, did])   // детей на keep
                    if let mt = movesTable {
                        try? db.run("UPDATE \(mt) SET from_id=? WHERE from_id=?", [keep, did])       // связки ребаланса
                        try? db.run("UPDATE \(mt) SET to_id=? WHERE to_id=?", [keep, did])
                    }
                    try? db.run("DELETE FROM \(table) WHERE id=?", [did])
                }
            }
        }
    }

    // Разовая чистка целевого от ТОЧНЫХ дублей, раскиданных по разным категориям (одинаковое имя + value +
    // валюта — идентичные копии от синхрона; parent игнорируем). Оставляем min(id), заполненные планы/поля,
    // детей и связки переносим на keep. Агрессивно (игнор parent) → только точные совпадения и только целевой.
    static func dedupeTargetExact(_ db: Database) {
        let mergeCols = ["target_value", "buy_value", "asset_type", "region", "note"]
        for _ in 0..<30 {
            guard let groups = try? db.rows("SELECT MIN(id) AS keep, COUNT(*) AS c FROM target_items GROUP BY LOWER(TRIM(name)), IFNULL(value,-999999.0), IFNULL(currency,'€') HAVING c > 1"),
                  !groups.isEmpty else { return }
            for g in groups {
                let keep = intval(g["keep"])
                guard let kp = (try? db.rows("SELECT name, value, currency FROM target_items WHERE id=?", [keep]))?.first,
                      let dups = try? db.rows("SELECT * FROM target_items WHERE LOWER(TRIM(name))=LOWER(TRIM(?)) AND IFNULL(value,-999999.0)=IFNULL(?,-999999.0) AND IFNULL(currency,'€')=IFNULL(?,'€') AND id<>?",
                        [kp["name"] ?? "", kp["value"] ?? NSNull(), kp["currency"] ?? NSNull(), keep]) else { continue }
                for d in dups {
                    let did = intval(d["id"])
                    for c in mergeCols {   // не терять план/тип/регион, если у keep пусто
                        if let v = d[c], !(v is NSNull), !((v as? String)?.isEmpty ?? false) {
                            try? db.run("UPDATE target_items SET \(c)=? WHERE id=? AND (\(c) IS NULL OR \(c)='')", [v, keep])
                        }
                    }
                    try? db.run("UPDATE target_items SET parent_id=? WHERE parent_id=?", [keep, did])
                    try? db.run("UPDATE target_moves SET from_id=? WHERE from_id=?", [keep, did])
                    try? db.run("UPDATE target_moves SET to_id=? WHERE to_id=?", [keep, did])
                    try? db.run("DELETE FROM target_items WHERE id=?", [did])
                }
            }
        }
    }

    // Техника «Дневник настройки» — объёмный образ себя (какой я / что делаю / что имею).
    // Создаём практику (17 вопросов) и один раз заполняем образ, если журнал пуст.
    static func ensureTuningDiary(_ db: Database) {
        let questions = [
            "Какой я? · Кем я являюсь через 3–6 месяцев?",
            "Какой я? · Как я отношусь к себе?",
            "Какой я? · Как я реагирую на сложности?",
            "Какой я? · Какие качества стали привычными и проявляются легко и естественно?",
            "Какой я? · Какие эмоции я испытываю? Какие ощущения в теле?",
            "Что я делаю? · Как выглядит мой обычный день?",
            "Что я делаю? · Что я делаю регулярно и без внутреннего сопротивления?",
            "Что я делаю? · Как я организую своё время?",
            "Что я делаю? · Что я делаю иначе, чем раньше?",
            "Что я делаю? · Что в моей жизни стало рутиной, а не усилием?",
            "Что я делаю? · Что я чувствую, когда так живу? Как реагирует тело?",
            "Что я имею? · Что есть в моей жизни как результат?",
            "Что я имею? · Что для меня стало нормой?",
            "Что я имею? · Что я себе разрешаю иметь?",
            "Что я имею? · Какие ресурсы меня окружают (деньги, время, поддержка, возможности)?",
            "Что я имею? · В чём я чувствую устойчивость и опору?",
            "Что я имею? · Что это даёт мне в ощущениях? Как отражается в теле?",
        ]
        seedTechniqueOnce(db, flag: "tune_v1", name: "Дневник настройки", steps: questions,
            note: "образ себя в настоящем времени: какой я · что делаю · что имею. Поля широкие, правится со временем")

        if ((try? db.rows("SELECT value FROM settings WHERE key = 'tune_seed_v1'"))?.first?["value"]) as? String == "1" { return }
        guard let pid = ((try? db.rows("SELECT id FROM practices WHERE name LIKE 'Дневник настройки%' AND name NOT LIKE '%(пример)%'"))?.first?["id"]) as? Int else { return }
        let count = ((try? db.rows("SELECT count(*) AS c FROM practice_log WHERE practice_id = ?", [pid]))?.first?["c"]) as? Int ?? 0
        if count == 0 {
            let answers = [
                "Владею сеткой в несколько сотен сайтов.\nСистемно развиваю свои проекты: организовываю реализацию и закрываю гипотезы еженедельно, стабилизируя проекты в топе. Эффективно делегирую рутину или автоматизирую её. Моя работа — стратегическое планирование и описание, а не рутинное выполнение.\nИнвестор с пассивным доходом 60 тыс/год, покрываю базовые затраты без работы. 3 объекта недвижимости под сдачу — Киев / Варшава / Аликанте.\nВладелец личной недвижимости в ЕС в премиум-сегменте.\nВладею автопарком фан-авто, MX5 на ЕС-номерах.\nТревога понизилась с 8 до 3. Фокусируюсь на одном приоритете в течение дня и последователен. Разделяю мысли и то, как вижу мир, понимаю, что это не объективная реальность, а та, что вижу через свои искажения. Тревога ограничена в дне определённым часом.\nНаучился принимать решения в сложных ситуациях — проверяю, подходят ли они под мои цели, и больше не впадаю в ступор и тревогу.\nЦеню момент: в нерабочие часы концентрируюсь на здесь и сейчас, открываю новые места и опыт, живу в моменте.",
                "Нахожусь в психологическом балансе, не пилю себя за прошлые неудачи. Верю, что то, чем занимаюсь, приведёт к большим результатам, чем были.\nПроявляю потенциал через реализацию задуманного — от этого чувствую себя увереннее, больше хвалю себя.\nДоволен собой, хвалю за то, что превзошёл ожидания.\nГорд, что получилось диверсифицироваться и стабилизировать будущее своё и детей.\nРадуюсь, что закрыл свою детскую мечту.\nХвалю себя за такие дни, не печалюсь из-за пропусков.\nУверен, что могу делать свой выбор.\nИзучаю мир и, несмотря на весь опыт, даю себе удивляться и наслаждаться.",
                "Не переношу задачи, а закрываю или вычёркиваю на ревью недели/месяца. Если не знаю как — отхожу и думаю, не лезу кое-как. Понимаю, что сложности прокачают новый навык, и я в любом случае разберусь.\nМеня не пугают сложности — быстро нахожу, как их системно решить, и делегирую тем, кому доверяю.\nРешаю спокойно в отведённый час, не в укор основной деятельности. Не паникую от нагрузки: нет такого, что надо решать именно сейчас. Возможности всегда появляются.\nНахожу способы решить без будущих проблем, у меня есть все документы и возможности.\nЭто не сложности, а мой досуг.\nЯ уже реализовал всё, что задумывал, поэтому понимаю — всё решаемо.\nНет идеальных решений, есть достаточно хорошие; не откладываю то, к чему решил прийти.\nДля сложностей есть часы: в дне 20:00, в неделе — пара часов на выходных.",
                "Системность, придерживание утренней рутины и рабочих процессов.\nПланирование недели задач заранее, собранность, ведение дашбордов с отсевом текучки и технических моментов.\nТолерантнее к рискам портфеля и неопределённости — увеличиваю аллокацию на 10%, понимая, почему тезис актуален. Нет хаоса, есть план на любой сценарий. Выбираю антихрупкость: любой сценарий рынка переживу с доходом.\nНе спешу, действую размеренно, не смешиваю цели инвестиций и комфорта.\nНе суечусь.\nСпокойно сижу без отвлечений, концентрируясь на одной задаче.\nРешительность, когда нужно сделать шаг.\nВижу прикольное в моменте, в фокусе в диалоге и в ситуациях.",
                "Доволен собой, спокоен — приду к целям с большей вероятностью, чем когда-либо. Приятное утомление от того, что развиваюсь, а не задалбываюсь.\nСфокусирован, чувствую драйв, лёгкое самодовольство от результатов, прилив энергии.\nСпокоен — не пугает инфляция и остановка дохода, расслаблен психологически. Жизнь зафиксирована от фатализма.\nРассудителен, сконцентрирован, спокоен.\nСобран, спокоен.\nВесело — вокруг столько интересного.",
                "Начинаю с утренней рутины и планирования, дальше иду по списку — есть автоматизированные инструменты трекинга.\nВстаю в 9 без телефона, час делаю рутину, затем погружаюсь в спланированные процессы. Два блока дня — текучка и стратегический. Полдня выходного в среду и полный в воскресенье. Часть субботы — рабочие хвосты, полдня саморазвитие.\nВ выходной спокойно читаю про запланированное, расписываю категорию на все сценарии и постепенно каждую неделю/месяц делаю действия.\nВсе тревоги — в 20:00, проблемы — в субботу вечером и воскресенье.",
                "Иду по списку рутин — рабочих и бытовых.\nВстаю и придерживаюсь графика.\nДелаю запланированную задачу каждую неделю (иногда раз в 2 недели), двигающую портфель к целям.\nФормирую и корректирую роадмап: налоги/ВНЖ, балансы, планы по покупкам/тратам и главное — источники дохода, эффективность каждого евро.",
                "Есть расписание, встаю в 9, всегда закладываю 20 минут к встрече/поездке, чтобы не бежать. Планирую реалистично.\nСконцентрированно работаю, выделяю ретрит-время отдельно.\nМаксимум 1 час в среду на инвестиции и 3 часа на выходных.\nУтром пару часов делаю стратегию сам в тишине, ближе к 12:00 — с людьми, во второй половине раскидываю текучку.\nПереживания разрешаю себе в отведённые часы 20:00, разгребаю на выходных в чиловой обстановке на балконе.",
                "По-другому планирую время — с запасом.\nДаю себе восстановиться: 1 выходной, полдня буднего.\nИнвестициями занимаюсь точечно: тайминг — месяцы/годы, не дни. Возвращаюсь с энтузиазмом после отдыха, беру всего 1 сверху на выходных.\nЧётко выделяю основную задачу дня, описываю как сделать, сроки, как анализировать и что она должна дать в глобальном смысле.\nРешая проблемы, связываю их в один роадмап, где видны траты, налоги и сложности.",
                "Подъём в 9 утра, концентрация на нужных задачах и планирование дня.\nПланирование рабочей недели.\nРазбор 1 финансового направления по выходным, раз в 1–2 недели; выписываю идеи и вношу в расписание.\nРазбор основной задачи.\nДополнение роадмапа.",
                "Менее тревожный, более сфокусированный и осознанный, в тонусе, сильный, способный конкурировать и побеждать.\nЕсть интерес к жизни, бодрость духа; тело хочет тратить энергию на улице — падл, авто-трек.\nСпокойствие, расслабленность, уверенность в будущем.\nУверенно в своём будущем, реализованном.\nСпокоен, больше радости в будних днях, меньше тревоги.",
                "Начинают покрываться расходы на проекты от новых доходов, вижу, как это увеличить в разы.\nПоявляется возможность выбирать: авто для фана/комфорта, путешествия, реализация инвест-плана до 5 млн.\nНаращиваю капитал к цели 5 млн независимо от ситуации в мире. 3 объекта недвижимости (под сдачу), 1 млн+ в фонде, физическое золото, наличные балансы, коммерческое помещение, земля.\nПроекты начинают окупать вложения.\nСтабилизируются все сферы жизни — успеваю и восстановиться, и спланировать решения.",
                "Я всё успеваю и вижу новые результаты в работе.\nРост дохода от месяца к месяцу без инфляции уровня жизни.\nМогу думать не только о выживании, давать себе полноценные отдыхи в неделях, месяцах и годах — в путешествиях.\nЧувствовать себя хорошо даже после нагруженного дня — была концентрация, а не бега.\nОтдыхать головой после 20:00, не крутить до ночи сложности на подсознании.",
                "Стабилизировать хороший уровень жизни, планировать апгрейд авто и хобби-тачки; капитал растёт к первой цели 5 млн.\nБольшое количество активов — ООО с фондой, золотые депозиты, недвижимость на югах.\nСпокойный сон, концентрацию на других сферах жизни и возможность обеспечить стабильность себе и семье.",
                "Недвижимость для жизни, инвестиции, покрывающие путешествия и сверх-траты; выполняю годовые цели капитала +500к в год, совместное кафе.\nЧастный дом в тихом месте, пассивные источники (дивиденды) в размере годовых расходов, большие путешествия.\nВремя выходного дня, свободные вечера, пустая голова в отпуске. Слитки в UA/AU, доходная недвижимость в ЕС/UA (3 объекта), жилая, фонда, покрывающая дивидендами жизнь, земля под селом, объект в Испании для краткосрочной сдачи.",
                "В диверсификации — все виды активов в большом количестве (тотал 5 млн), источники дохода: бизнес в двух направлениях (белое и серое), офлайн-кафе.\nПоявляются источники дохода — дивиденды, несколько партнёрок + зарубежные, белый гео-проект для легализации, офлайн-истории.\nУстойчивость психики — научился жить со своим расфокусом: передвинул его запросы на одно время и дал получать своё в те часы.",
                "Интерес к жизни, эйфория от новых достижений, весело, в фокусе, чувствую энергию, которую хочу реализовывать.\nЧувствую себя на своём месте, нет зажимов, могу быть без масок.\nСпокойствие, концентрация в других сферах; тело расслаблено после работы, голова может насладиться гонками, треком.\nУровень навыков во всех сферах поднялся, быстрее принимаю решения. Легко дышать, голова мыслит здраво без суеты.\nТело расслаблено, высыпаюсь лучше, больше энергии на спорт, общение, семью. Нет постоянных переживаний, что что-то забыл или не решил.",
            ]
            let aj = String(data: (try? JSONSerialization.data(withJSONObject: answers)) ?? Data("[]".utf8), encoding: .utf8) ?? "[]"
            try? db.run("INSERT INTO practice_log(practice_id, date, note, answers) VALUES(?,?,?,?)", [pid, localToday(), "", aj])
        }
        try? setSetting(db, "tune_seed_v1", "1")
    }

    // Техника «Позитивное намерение» — 7 шагов. Создаёт практику (флаг pi_v1) и один раз
    // обновляет формулировку шагов у уже существующей практики (флаг pi_steps_v2).
    static func ensurePositiveIntent(_ db: Database) {
        let steps = [
            "Поведение / убеждение. Что делаю, что не делаю, какой результат, что думаю?",
            "Принятие. Есть причины, разрешаю это. Это сейчас лучший способ. Разрешаю себе понять и найти лучший способ.",
            "Позитивное намерение. Чтобы что получить? От чего защититься? Какие ситуации, чувства, ощущения?",
            "Что в результате? Насколько поведение/убеждение из п.1 помогает реализации позитивного намерения из п.3 (1–10)?",
            "Побочные эффекты? Какую цену я плачу? Какие нежелательные эффекты получаю от убеждения/поведения из п.1? Что теряю?",
            "Альтернативное поведение/мышление. Какое мышление и поведение поможет реализовать позитивное намерение (п.3) с меньшими побочными эффектами и большей эффективностью? Чему научиться, какой опыт получить?",
            "Конкретные действия. Какой первый шаг я выбираю (эксперимент)?",
        ]
        let stepsJson = String(data: (try? JSONSerialization.data(withJSONObject: steps)) ?? Data("[]".utf8), encoding: .utf8) ?? "[]"
        if let row = (try? db.rows("SELECT id FROM practices WHERE name LIKE 'Позитивное намерение%' AND name NOT LIKE '%(пример)%'"))?.first {
            if ((try? db.rows("SELECT value FROM settings WHERE key = 'pi_steps_v3'"))?.first?["value"]) as? String != "1" {
                try? db.run("UPDATE practices SET steps = ? WHERE id = ?", [stepsJson, intval(row["id"])])
            }
        } else if ((try? db.rows("SELECT value FROM settings WHERE key = 'pi_v1'"))?.first?["value"]) as? String != "1" {
            let ord = nextOrd(db, "SELECT COALESCE(MAX(ord),0)+1 AS o FROM practices")
            try? db.run("INSERT INTO practices(name, kind, days, time, steps, note, ord) VALUES(?,?,?,?,?,?,?)",
                ["Позитивное намерение", "technique", "", NSNull(), stepsJson,
                 "за поведением/убеждением стоит позитивное намерение — найди его, оцени цену и подбери более эффективную альтернативу", ord])
        }
        try? setSetting(db, "pi_v1", "1")
        try? setSetting(db, "pi_steps_v3", "1")
    }

    // Разобранные случаи в журнал «Дневника мыслей» — вносим один раз (флаг td_seed_v1),
    // только если журнал пуст (чтобы не задвоить при синхроне Mac↔iPhone).
    static func seedThoughtDiaryEntries(_ db: Database) {
        if ((try? db.rows("SELECT value FROM settings WHERE key = 'td_seed_v1'"))?.first?["value"]) as? String == "1" { return }
        guard let pid = ((try? db.rows("SELECT id FROM practices WHERE name LIKE 'Дневник мыслей%' AND name NOT LIKE '%(пример)%'"))?.first?["id"]) as? Int else { return }
        let count = ((try? db.rows("SELECT count(*) AS c FROM practice_log WHERE practice_id = ?", [pid]))?.first?["c"]) as? Int ?? 0
        if count == 0 {
            let entries: [[String]] = [
                ["19:00 Собираюсь решить задачи, хвосты где есть сложные решения",
                 "Нужно чуть позже, собраться силами, возможно сейчас ещё можно не париться и потом подумаю (50)",
                 "Беспокойство (90)",
                 "Откладываю и не сажусь за задачу, нахожу причины не успевать. Нужно расписать текущее видение, там где сомневаюсь — указать, пересмотреть через какое время и почему."],
                ["18:00 Планирую разговор с Серым по переводам",
                 "Сейчас уже поздно, выходной, не хочу беспокоить, надо просчитать всё (90)",
                 "Сомнение (100)",
                 "Надо посчитать спокойно, спланировать удобный для двоих день и свои ожидания. Ставлю задачу в неудобный момент, не подумав, что хочу получить точно и устроит ли меня какой из вариантов."],
            ]
            for answers in entries {
                let aj = String(data: (try? JSONSerialization.data(withJSONObject: answers)) ?? Data("[]".utf8), encoding: .utf8) ?? "[]"
                _ = try? db.run("INSERT INTO practice_log(practice_id, date, note, answers) VALUES(?,?,?,?)",
                    [pid, localToday(), "", aj])
            }
        }
        try? setSetting(db, "td_seed_v1", "1")
    }

    // Каркас портфеля: 4 блока + замороженный капитал с примерами (порт ensurePortfolio).
    private static func ensurePortfolio(_ db: Database) throws {
        if ((try db.rows("SELECT count(*) AS c FROM portfolio_items").first?["c"]) as? Int ?? 0) > 0 { return }
        func ins(_ parent: Int?, _ name: String, _ kind: String, value: Double? = nil) throws -> Int {
            let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM portfolio_items WHERE parent_id IS ?", [parent]).first?["o"]))
            return try db.run("INSERT INTO portfolio_items(parent_id, ord, name, kind, value) VALUES(?,?,?,?,?)",
                              [parent, ord, name, kind, value as Any?])
        }
        _ = try ins(nil, "Блок защиты", "block")
        _ = try ins(nil, "Блок роста", "block")
        _ = try ins(nil, "Блок развития", "block")
        let frozen = try ins(nil, "Замороженный капитал", "block")
        let re = try ins(frozen, "Недвижимость", "section")
        _ = try ins(re, "Start", "asset", value: 100000)
        _ = try ins(re, "Belgravia", "asset", value: 300000)
        let pas = try ins(frozen, "Пассивы", "section")
        _ = try ins(pas, "X5", "asset", value: 45000)
        _ = try ins(pas, "MX5", "asset", value: 30000)
    }

    // Строки курсов, чтобы их можно было править вручную даже без сети (порт ensureRates).
    private static func ensureRates(_ db: Database) throws {
        try db.run("UPDATE portfolio_items SET rate_symbol = NULL WHERE rate_symbol = '^SPX'")
        try db.run("DELETE FROM rates WHERE symbol = '^SPX'")
        let defs = [("XAUUSD", "Золото"), ("EURUSD", "EUR/USD"), ("BTCUSD", "BTC"),
                    ("SCHD", "SCHD"), ("IVV", "IVV"), ("VHT", "VHT")]
        for (sym, label) in defs {
            try db.run("INSERT OR IGNORE INTO rates(symbol, label) VALUES(?,?)", [sym, label])
        }
    }

    // ⚡ Энергия жизни + Банк впечатлений — структура против шаблона (порт ensureEnergy).
    private static func ensureEnergy(_ db: Database) throws {
        var energy = (try db.rows("SELECT id FROM nodes WHERE is_category = 1 AND parent_id IS NULL AND title LIKE '%Энергия жизни%'").first?["id"]) as? Int
        if energy == nil { energy = try insertNode(db, parentId: nil, title: "⚡ Энергия жизни", note: "", isCategory: 1) }
        if let e = energy,
           (try db.rows("SELECT id FROM nodes WHERE is_category = 1 AND parent_id = ? AND title LIKE '%Банк впечатлений%'", [e]).first) == nil {
            _ = try insertNode(db, parentId: e, title: "Банк впечатлений", note: "", isCategory: 1)
        }
    }

    static func insertNode(_ db: Database, parentId: Int?, title: String, note: String, isCategory: Int) throws -> Int {
        let ord = Int(num(try db.rows("SELECT COALESCE(MAX(ord),0)+1 AS o FROM nodes WHERE parent_id IS ?", [parentId]).first?["o"]))
        // updated_at ставим в localtime (как правки/tombstones) — иначе новый узел по UTC-дефолту
        // выглядит «старше» tombstone переиспользованного id и merge его удаляет (исчезает после синхрона)
        let id = try db.run("INSERT INTO nodes(parent_id, ord, title, note, is_category, updated_at) VALUES(?,?,?,?,?, datetime('now','localtime'))",
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
            let status: Any
            if kind == "decision" { status = "open" }
            else if kind == "task" { status = "todo" }
            else { status = NSNull() }
            f["status"] = status
            keys.append("status")
        }
        let sets = keys.map { "\($0) = ?" }.joined(separator: ", ")
        var params: [Any?] = keys.map { f[$0] }
        params.append(id)
        try db.run("UPDATE nodes SET \(sets), updated_at = datetime('now','localtime') WHERE id = ?", params)
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
        // любой некатегорийный узел со сроком можно отметить (вопрос/идея/цель/тревога/без типа) — иначе не закрыть из «Сегодня»/календаря
        guard intval(t["is_category"]) == 0 else { return t }
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
        // дата закрытия задачи — для счётчиков «закрытые задачи за период»
        if next == "done" || next == "accepted" { try? db.run("UPDATE nodes SET completed_at = COALESCE(completed_at, ?) WHERE id = ?", [localToday(), id]) }
        else { try? db.run("UPDATE nodes SET completed_at = NULL WHERE id = ?", [id]) }
        return res
    }

    private static func shiftRepeat(_ iso: String, _ rep: String) -> String {
        if rep == "weekly", let d = ymdUTC.date(from: iso) {
            return ymdUTC.string(from: d.addingTimeInterval(7 * 86400))
        }
        return addMonths(iso, rep == "yearly" ? 12 : 1)
    }

    static func reorderNode(_ db: Database, id: Int, refId: Int, pos w: String) throws -> [String: Any]? {
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
        try db.run("UPDATE nodes SET parent_id = ?, updated_at = datetime('now','localtime') WHERE id = ?", [refParent, id])
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
        try db.run("UPDATE nodes SET parent_id = ?, ord = ?, updated_at = datetime('now','localtime') WHERE id = ?", [newParent, ord, id])
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
    static func portfolioTree(_ db: Database, _ table: String = "portfolio_items") throws -> [[String: Any]] {
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
        for var r in try db.rows("SELECT * FROM \(table) ORDER BY parent_id NULLS FIRST, ord, id") {
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
        let target: Double? = isLeaf ? numOpt(r["target_value"]).flatMap { toEur($0, cur) } : (anyNonNull("target") ? sum("target") : nil)   // план в €, агрегируется по узлам
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
        _ = try? db.run("INSERT OR IGNORE INTO snapshots(date, portfolio_eur) VALUES(?,?)", [localToday(), portfolioTotal])  // снимок раз в день
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
        // аллокация по регионам инвестиции (SK/UA/AU/EU/WEB)
        var byRegion: [String: Double] = [:]
        var byRegionBlocks: [String: [String: Double]] = [:]
        func walkRegion(_ n: [String: Any], _ rootName: String) {
            let children = n["children"] as? [[String: Any]] ?? []
            let isLeaf = (n["kind"] as? String) == "asset" || children.isEmpty
            if isLeaf, let e = n["eur"] as? Double, e != 0 {
                let rg = (n["region"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? "без региона"
                byRegion[rg, default: 0] += e
                byRegionBlocks[rg, default: [:]][rootName, default: 0] += e
            }
            for c in children { walkRegion(c, rootName) }
        }
        for b in portfolio { walkRegion(b, b["name"] as? String ?? "") }
        let byRegionSorted: [[Any]] = byRegion.sorted { $0.value > $1.value }.map { [$0.key, $0.value] }
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
            let principal = num(i["principal"]), irate = num(i["rate"])
            let m: Double
            if principal > 0 && irate > 0 {
                let perPeriod = principal * irate / 100
                m = (i["rate_period"] as? String) == "monthly" ? perPeriod : perPeriod / 12
            } else {
                let p = i["period"] as? String
                m = p == "monthly" ? num(i["amount"]) : p == "yearly" ? num(i["amount"]) / 12 : 0
            }
            return acc + ((i["currency"] as? String) == "$" ? m / rate : m)
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
        let budgetItems = try db.rows("SELECT * FROM budget_items ORDER BY direction DESC, ord, id")   // дефолтные расходы/доходы (списком)
        let targetPortfolio = try portfolioTree(db, "target_items")   // целевой портфель — отдельное дерево (та же структура, своё наполнение)
        let targetMoves = try db.rows("SELECT * FROM target_moves")   // ручные связки ребаланса (откуда→куда)
        // аллокация по типам активов для целевого (как в факте)
        var tByType: [String: Double] = [:]
        var tByTypeBlocks: [String: [String: Double]] = [:]
        func walkTypeT(_ n: [String: Any], _ rootName: String) {
            let children = n["children"] as? [[String: Any]] ?? []
            let isLeaf = (n["kind"] as? String) == "asset" || children.isEmpty
            if isLeaf, let e = n["eur"] as? Double, e != 0 {
                let ty = n["asset_type"] as? String ?? "без типа"
                tByType[ty, default: 0] += e
                tByTypeBlocks[ty, default: [:]][rootName, default: 0] += e
            }
            for c in children { walkTypeT(c, rootName) }
        }
        for b in targetPortfolio { walkTypeT(b, b["name"] as? String ?? "") }
        let tByTypeSorted: [[Any]] = tByType.sorted { $0.value > $1.value }.map { [$0.key, $0.value] }
        let rates = try db.rows("SELECT * FROM rates")
        let result: [String: Any] = [
            "accounts": accounts, "portfolio": portfolio, "steps": steps,
            "obligations": obligations, "loans": loans, "debts": debts,
            "snapshotDelta": snapshotDelta,
            "byType": byTypeSorted, "byTypeBlocks": byTypeBlocks, "byRegion": byRegionSorted, "byRegionBlocks": byRegionBlocks, "blockEur": blockEur,
            "tx": tx, "forecasts": fc, "properties": props, "fire": fireV,
            "income": income, "budget": budget, "budgetItems": budgetItems, "targetPortfolio": targetPortfolio, "targetMoves": targetMoves, "targetByType": tByTypeSorted, "targetByTypeBlocks": tByTypeBlocks, "macro": macro, "rates": rates,
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
            SELECT id, title, kind, status, priority, due_date, due_time FROM nodes
            WHERE due_date BETWEEN ? AND ? AND is_category = 0
            """, [first, last]) {
            let st = t["status"] as? String ?? ""
            items.append(["date": t["due_date"] ?? NSNull(), "type": "task", "id": t["id"] ?? NSNull(),
                "title": t["title"] ?? NSNull(), "done": ["done", "accepted"].contains(st),
                "kind": t["kind"] ?? NSNull(), "priority": t["priority"] ?? NSNull(), "time": t["due_time"] ?? NSNull()])
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
        let eventDone = Set(try db.rows("SELECT event_id, date FROM event_done").map { "\(intval($0["event_id"])):\($0["date"] as? String ?? "")" })
        for e in try db.rows("SELECT * FROM events") {
            for d in occurrences(e["date"] as? String, e["recur"] as? String, first, last) {
                items.append(["date": d, "type": "event", "id": e["id"] ?? NSNull(), "title": e["title"] ?? NSNull(),
                    "time": e["time"] ?? NSNull(), "recur": e["recur"] ?? NSNull(),
                    "done": eventDone.contains("\(intval(e["id"])):\(d)")])
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
                SELECT id, title, kind, priority, due_date, due_time, repeat FROM nodes
                WHERE is_category = 0 AND (status IS NULL OR status NOT IN ('done','accepted')) AND \(cond)
                ORDER BY priority IS NULL, priority, due_date
                """, [t])
        }
        let overdue = try taskRows("due_date < ?")
        let dueToday = try taskRows("due_date = ?")
        // обязательства с подошедшей/просроченной датой — наравне с задачами (пока не оплачены — оплата двигает next_date вперёд)
        let obToday = try db.rows("SELECT id, name, amount, currency, next_date, due_time, period, kind FROM obligations WHERE next_date = ? ORDER BY due_time IS NULL, due_time", [t])
        var obOverdue = try db.rows("SELECT id, name, amount, currency, next_date, due_time, period, kind FROM obligations WHERE next_date < ? ORDER BY next_date", [t])
        for i in obOverdue.indices {
            obOverdue[i]["overdue_days"] = (obOverdue[i]["next_date"] as? String).flatMap { dayDiff($0, t) }.map { Int(floor($0)) } ?? NSNull()
        }
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
        let events = all.filter { ($0["type"] as? String) == "event" && (dateOf($0) == t || dateOf($0) == tomorrow) && !(($0["done"] as? Bool) ?? false) }
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
            FROM nodes WHERE is_category = 0 AND due_date BETWEEN ? AND ?
            """, [monday, sunday]).first
        let checkin = try db.rows("SELECT mood, note FROM checkins WHERE date = ?", [t]).first
        let real = (try db.rows("SELECT count(*) AS c FROM nodes WHERE is_category = 0").first?["c"] as? Int) ?? 0
        let typed = (try db.rows("SELECT count(*) AS c FROM nodes WHERE is_category = 0 AND kind IS NOT NULL").first?["c"] as? Int) ?? 0
        let inboxCat = try db.rows("SELECT id FROM nodes WHERE is_category = 1 AND title LIKE '%Инбокс%'").first
        let inboxId = inboxCat.map { intval($0["id"]) }
        let inbox = inboxId != nil
            ? ((try db.rows("SELECT count(*) AS c FROM nodes WHERE parent_id = ?", [inboxId!]).first?["c"] as? Int) ?? 0) : 0
        let practicesToday = ((try? monthOccurrences(db, ym, t, t)) ?? [])
            .filter { dateOf($0) == t && !(($0["done"] as? Bool) ?? false) }.count
        let routinesArr = (try? JSONSerialization.jsonObject(with: try routines(db))) as? [[String: Any]] ?? []
        let result: [String: Any] = [
            "date": t,
            "activityMonth": (try db.rows("SELECT value FROM settings WHERE key = 'activity_month'").first?["value"]) ?? NSNull(),
            "focusOrder": (try db.rows("SELECT value FROM settings WHERE key = 'focus_order'").first?["value"]) ?? NSNull(),
            "routines": sortRoutines(routinesArr),
            "overdue": overdue, "dueToday": dueToday, "obToday": obToday, "obOverdue": obOverdue, "week": week, "events": events,
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
              AND status IN ('done','accepted') AND updated_at >= datetime('now','localtime','-7 days')
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

    static func practiceStreak(_ db: Database, id: Int, days: String?) throws -> Int {
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

    // ===== Синхронизация Mac↔iPhone: снимок всей базы и его применение =====
    // Все реальные таблицы данных (FTS-таблицы node_fts/page_fts производные —
    // их не переносим, а перестраиваем из nodes/pages после применения снимка).
    static let syncTables = ["nodes", "links", "dismissed", "accounts", "portfolio_classes",
        "steps", "obligations", "portfolio_items", "rates", "events", "transactions", "budget_items", "target_items", "target_moves",
        "receivables", "passive_income", "settings", "macro_notes", "debts", "snapshots",
        "routines", "routine_log", "people", "contact_log", "pages", "page_revisions", "attachments",
        "practices", "practice_log", "wheel_areas", "wheel_scores", "area_milestones", "area_questions", "work_log", "forecasts",
        "properties", "checkins", "metrics", "metric_log", "node_log", "trash", "event_done"]

    // Таблицы с одним ключом → двусторонний merge по updated_at (LWW) + tombstones.
    static let syncKeyed: [(String, String)] = [
        ("nodes", "id"), ("links", "id"), ("accounts", "id"), ("portfolio_classes", "id"),
        ("steps", "id"), ("obligations", "id"), ("portfolio_items", "id"), ("events", "id"),
        ("transactions", "id"), ("receivables", "id"), ("passive_income", "id"), ("macro_notes", "id"),
        ("budget_items", "id"), ("target_items", "id"), ("target_moves", "id"), ("debts", "id"), ("routines", "id"), ("people", "id"), ("contact_log", "id"),
        ("pages", "id"), ("page_revisions", "id"), ("attachments", "id"), ("practices", "id"), ("practice_log", "id"),
        ("wheel_areas", "id"), ("wheel_scores", "id"), ("area_milestones", "id"), ("area_questions", "id"), ("work_log", "id"), ("forecasts", "id"),
        ("properties", "id"), ("metrics", "id"), ("node_log", "id"), ("trash", "id"),
        ("settings", "key"), ("rates", "symbol"), ("snapshots", "date"), ("checkins", "date")]
    // Таблицы с составным ключом (логи/отметки) → простое объединение, без tombstones.
    static let syncUnion = ["dismissed", "routine_log", "metric_log", "event_done"]

    // Миграция для синхрона: updated_at на всех таблицах + триггеры (поддерживают
    // updated_at на правках и пишут tombstones при удалении — БЕЗ изменения кода мутаций).
    // Всё через try? — даже если что-то не так, открытие базы не падает. Время — localtime
    // (как updateNode), один пользователь = один часовой пояс, сравнения корректны.
    static func ensureSyncSchema(_ db: Database) {
        _ = try? db.run("CREATE TABLE IF NOT EXISTS sync_tombstones(tbl TEXT, row_key TEXT, deleted_at TEXT, PRIMARY KEY(tbl,row_key))")
        // закрытые («выполнено») даты событий — миграция существующих баз (повтор не удаляется)
        _ = try? db.run("CREATE TABLE IF NOT EXISTS event_done(event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE, date TEXT NOT NULL, UNIQUE(event_id, date))")
        for (t, k) in syncKeyed {
            _ = try? db.run("ALTER TABLE \(t) ADD COLUMN updated_at TEXT")          // тихо, если уже есть
            // строки без времени (до sync-эры) помечаем ДРЕВНЕЙ датой, НЕ now: иначе при первом запуске
            // sync-версии все строки разом «свежеют» и затирают реальные правки другого устройства (портфель
            // откатывался к старым суммам). Древняя дата → любая настоящая правка выигрывает LWW.
            _ = try? db.run("UPDATE \(t) SET updated_at = '2000-01-01 00:00:00' WHERE updated_at IS NULL")
            // новая строка из приложения без времени → проставить (merge-вставки время задают сами)
            _ = try? db.run("""
                CREATE TRIGGER IF NOT EXISTS \(t)_stamp AFTER INSERT ON \(t)
                WHEN NEW.updated_at IS NULL
                BEGIN UPDATE \(t) SET updated_at = datetime('now','localtime') WHERE \(k) = NEW.\(k); END
                """)
            // правка в приложении (updated_at не менялся самим запросом) → проставить время
            _ = try? db.run("""
                CREATE TRIGGER IF NOT EXISTS \(t)_touch AFTER UPDATE ON \(t)
                WHEN OLD.updated_at = NEW.updated_at
                BEGIN UPDATE \(t) SET updated_at = datetime('now','localtime') WHERE \(k) = NEW.\(k); END
                """)
            // удаление → tombstone (чтобы удаление доехало на второе устройство)
            _ = try? db.run("""
                CREATE TRIGGER IF NOT EXISTS \(t)_tomb AFTER DELETE ON \(t)
                BEGIN INSERT OR REPLACE INTO sync_tombstones(tbl,row_key,deleted_at)
                      VALUES('\(t)', OLD.\(k), datetime('now','localtime')); END
                """)
        }
    }

    // Полный снимок: данные + tombstones + фронтенд. Источник истины для слияния.
    static func syncSnapshot(_ db: Database) throws -> [String: Any] {
        ensureSyncSchema(db)
        var tables: [String: Any] = [:]
        for t in syncTables { tables[t] = (try? db.rows("SELECT * FROM \(t)")) ?? [] }
        let tomb = (try? db.rows("SELECT tbl, row_key, deleted_at FROM sync_tombstones")) ?? []
        return ["version": 3, "generated_at": isoNow(), "tables": tables, "tombstones": tomb, "web": frontendBundle()]
    }

    // Бэкап файла зашифрованной базы: локально (backups/, 10 последних) + оффсайт в iCloud Drive
    // (Pipboy-backups/, 30 последних). daily=true → не чаще одного раза в сутки (авто-бэкап при запуске);
    // daily=false → всегда (перед слиянием при синхроне, «на всякий случай»).
    static func backupDB(daily: Bool = false) {
        guard let src = try? Database.fileURL(), FileManager.default.fileExists(atPath: src.path) else { return }
        let fm = FileManager.default
        let dir = src.deletingLastPathComponent().appendingPathComponent("backups", isDirectory: true)
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        if daily {   // уже есть копия за сегодня — не плодим
            let today = String(isoNow().prefix(10))
            if let all = try? fm.contentsOfDirectory(atPath: dir.path),
               all.contains(where: { $0.hasPrefix("pipboy-\(today)") && $0.hasSuffix(".db") }) { return }
        }
        let stamp = isoNow().replacingOccurrences(of: ":", with: "-").replacingOccurrences(of: " ", with: "_")
        try? fm.copyItem(at: src, to: dir.appendingPathComponent("pipboy-\(stamp).db"))
        if let all = try? fm.contentsOfDirectory(atPath: dir.path).filter({ $0.hasSuffix(".db") }).sorted() {
            for f in all.dropLast(10) { try? fm.removeItem(at: dir.appendingPathComponent(f)) }
        }
        backupOffsite(src, stamp)
    }

    // Оффсайт-копия в iCloud Drive (только macOS; если iCloud Drive не подключён — тихо пропускаем).
    // Файл зашифрован SQLCipher, без ключа бесполезен, поэтому облачное хранение безопасно.
    static func backupOffsite(_ src: URL, _ stamp: String) {
        #if os(macOS)
        let fm = FileManager.default
        let cloud = fm.homeDirectoryForCurrentUser
            .appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs", isDirectory: true)
        guard fm.fileExists(atPath: cloud.path) else { return }   // iCloud Drive выключен — оффсайт пропускаем
        let dir = cloud.appendingPathComponent("Pipboy-backups", isDirectory: true)
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        try? fm.copyItem(at: src, to: dir.appendingPathComponent("pipboy-\(stamp).db"))
        if let all = try? fm.contentsOfDirectory(atPath: dir.path).filter({ $0.hasSuffix(".db") }).sorted() {
            for f in all.dropLast(30) { try? fm.removeItem(at: dir.appendingPathComponent(f)) }
        }
        #endif
    }


    // Все файлы фронта (из webRoot источника) в base64. На Mac webRoot = живой app/public.
    static func frontendBundle() -> [String: String] {
        var out: [String: String] = [:]
        let base = PipboySchemeHandler.webRoot.standardizedFileURL
        guard let en = FileManager.default.enumerator(at: base, includingPropertiesForKeys: [.isRegularFileKey]) else { return out }
        for case let url as URL in en {
            guard (try? url.resourceValues(forKeys: [.isRegularFileKey]))?.isRegularFile == true else { continue }
            let rel = url.standardizedFileURL.path.replacingOccurrences(of: base.path + "/", with: "")
            if rel.contains("..") { continue }
            if let data = try? Data(contentsOf: url) { out[rel] = data.base64EncodedString() }
        }
        return out
    }

    // Записать полученный фронт в webDir (iPhone) — webRoot станет читать отсюда.
    static func applyFrontend(_ web: [String: String]) throws {
        let fm = FileManager.default
        let base = PipboySchemeHandler.webDir
        try? fm.removeItem(at: base)
        try fm.createDirectory(at: base, withIntermediateDirectories: true)
        for (rel, b64) in web {
            if rel.contains("..") || rel.hasPrefix("/") { continue }
            guard let data = Data(base64Encoded: b64) else { continue }
            let dest = base.appendingPathComponent(rel)
            try? fm.createDirectory(at: dest.deletingLastPathComponent(), withIntermediateDirectories: true)
            try? data.write(to: dest)
        }
    }

    // Применить снимок «заменой»: получатель полностью берёт данные отправителя.
    // Для бутстрапа (iPhone пустой) это ровно то, что нужно. Двусторонний LWW — отдельный этап.
    static func syncApplyReplace(_ db: Database, _ snapshot: [String: Any]) throws {
        guard let tables = snapshot["tables"] as? [String: Any] else { throw Unsupported(path: "плохой снимок") }
        try db.run("PRAGMA foreign_keys = OFF")   // на время массовой замены — вне транзакции (внутри PRAGMA игнорится)
        defer { _ = try? db.run("PRAGMA foreign_keys = ON") }
        try db.run("BEGIN")
        do {
            for t in syncTables {
                try db.run("DELETE FROM \(t)")
                guard let rows = tables[t] as? [[String: Any]] else { continue }
                for row in rows {
                    let cols = knownKeys(db, t, row)
                    guard !cols.isEmpty else { continue }
                    let colList = cols.map { "\"\($0)\"" }.joined(separator: ",")
                    let marks = cols.map { _ in "?" }.joined(separator: ",")
                    let vals: [Any?] = cols.map { c in let v = row[c]; return (v is NSNull) ? nil : v }
                    try db.run("INSERT INTO \(t)(\(colList)) VALUES(\(marks))", vals)
                }
            }
            try rebuildFTS(db)   // перестроить поисковые индексы из nodes/pages
            try db.run("COMMIT")
        } catch {
            _ = try? db.run("ROLLBACK")
            throw error
        }
        // фронт — вне транзакции БД: если приехал, обновляем веб-интерфейс на приёмнике
        if let web = snapshot["web"] as? [String: String], !web.isEmpty { try? applyFrontend(web) }
    }

    // Двусторонний merge: вставка новых, LWW по updated_at для существующих,
    // применение tombstones (удаления). Перед слиянием — авто-бэкап базы.
    @discardableResult
    static func syncApplyMerge(_ db: Database, _ snapshot: [String: Any], applyWeb: Bool = true) throws -> Int {
        // merge идёт по отдельному соединению, минуя database()/сид — гарантируем ПОЛНУЮ схему,
        // иначе строки для ещё не созданных таблиц (wheel_areas, area_milestones, area_questions, budget_items…)
        // молча отбрасываются (tableColumns пусто) и данные не приезжают на второе устройство.
        try? db.ensureSchema()
        ensureSpheresSchema(db)
        _ = try? db.run("CREATE TABLE IF NOT EXISTS budget_items(id INTEGER PRIMARY KEY, direction TEXT NOT NULL DEFAULT 'expense', name TEXT NOT NULL DEFAULT '', amount REAL NOT NULL DEFAULT 0, currency TEXT NOT NULL DEFAULT '€', ord INTEGER NOT NULL DEFAULT 0, month TEXT)")
        if !(((try? db.rows("PRAGMA table_info(target_items)")) ?? []).contains { ($0["name"] as? String) == "parent_id" }) {
            _ = try? db.run("DROP TABLE IF EXISTS target_items")   // старая плоская схема → пересоздаём как дерево
        }
        _ = try? db.run("CREATE TABLE IF NOT EXISTS target_items(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES target_items(id) ON DELETE CASCADE, ord INTEGER NOT NULL DEFAULT 0, name TEXT NOT NULL DEFAULT '', kind TEXT NOT NULL DEFAULT 'asset', value REAL, buy_value REAL, target_value REAL, currency TEXT NOT NULL DEFAULT '€', asset_type TEXT, qty REAL, rate_symbol TEXT, note TEXT)")
        _ = try? db.run("CREATE TABLE IF NOT EXISTS target_moves(id INTEGER PRIMARY KEY, from_id INTEGER REFERENCES target_items(id) ON DELETE CASCADE, to_id INTEGER REFERENCES target_items(id) ON DELETE CASCADE, amount REAL NOT NULL DEFAULT 0)")
        ensureSyncSchema(db)
        backupDB()
        guard let tables = snapshot["tables"] as? [String: Any] else { throw Unsupported(path: "плохой снимок") }
        let peerTomb = (snapshot["tombstones"] as? [[String: Any]]) ?? []
        var changed = 0   // сколько РЕАЛЬНЫХ изменений данных применили (0 → экран не дёргаем)
        try db.run("PRAGMA foreign_keys = OFF")
        defer { _ = try? db.run("PRAGMA foreign_keys = ON") }
        try db.run("BEGIN")
        do {
            // 1) строки: вставить новые / обновить более свежими (LWW)
            for (t, key) in syncKeyed {
                guard let rows = tables[t] as? [[String: Any]] else { continue }
                for row in rows {
                    guard let rkAny = row[key], !(rkAny is NSNull) else { continue }
                    let rk = "\(rkAny)"
                    let inTs = (row["updated_at"] as? String) ?? ""
                    // локально удалено позже, чем правка с того устройства → удаление побеждает
                    if let delTs = scalarStr(db, "SELECT deleted_at FROM sync_tombstones WHERE tbl=? AND row_key=?", [t, rk]),
                       delTs >= inTs { continue }
                    if !existsRow(db, t, key, rkAny) {
                        try upsertRow(db, t, row, replaceKey: nil, keyCol: key, rk: rkAny); changed += 1   // новой строки нет → вставить
                    } else if inTs > (scalarStr(db, "SELECT updated_at FROM \(t) WHERE \(key)=?", [rkAny]) ?? "") {
                        try upsertRow(db, t, row, replaceKey: true, keyCol: key, rk: rkAny); changed += 1   // входящая свежее → обновить
                    }   // иначе локальная свежее → оставить
                }
            }
            // 2) применить входящие удаления
            for tomb in peerTomb {
                guard let t = tomb["tbl"] as? String,
                      let pair = syncKeyed.first(where: { $0.0 == t }),
                      let rkAny = tomb["row_key"], !(rkAny is NSNull) else { continue }
                let key = pair.1
                let del = (tomb["deleted_at"] as? String) ?? ""
                let rk = "\(rkAny)"
                if let localTs = scalarStr(db, "SELECT updated_at FROM \(t) WHERE \(key)=?", [rkAny]), del > localTs {
                    // удаление практики-дубля с одного устройства не должно уносить журнал/расписание на этом:
                    // сперва переносим practice_log на одноимённую оставшуюся практику (иначе ON DELETE CASCADE
                    // сотрёт записи, а их tombstone уедет обратно и удалит уже слитые — дневник пустел)
                    if t == "practices", let nm = scalarStr(db, "SELECT name FROM practices WHERE id=?", [rkAny]),
                       let keep = (try? db.rows("SELECT MIN(id) AS k FROM practices WHERE name=? AND id<>?", [nm, rkAny]))?.first?["k"], !(keep is NSNull) {
                        try? db.run("UPDATE practice_log SET practice_id=? WHERE practice_id=?", [intval(keep), rkAny])
                    }
                    // то же для факта и целевого: удаление дубля-категории не должно уносить вложенные позиции/связки
                    if t == "portfolio_items" || t == "target_items", let info = try? db.rows("SELECT parent_id, name FROM \(t) WHERE id=?", [rkAny]).first,
                       let keep = (try? db.rows("SELECT MIN(id) AS k FROM \(t) WHERE IFNULL(parent_id,-1)=IFNULL(?,-1) AND LOWER(TRIM(name))=LOWER(TRIM(?)) AND id<>?", [info["parent_id"] ?? NSNull(), info["name"] ?? "", rkAny]))?.first?["k"], !(keep is NSNull) {
                        try? db.run("UPDATE \(t) SET parent_id=? WHERE parent_id=?", [intval(keep), rkAny])
                        if t == "target_items" {
                            try? db.run("UPDATE target_moves SET from_id=? WHERE from_id=?", [intval(keep), rkAny])
                            try? db.run("UPDATE target_moves SET to_id=? WHERE to_id=?", [intval(keep), rkAny])
                        }
                    }
                    try db.run("DELETE FROM \(t) WHERE \(key)=?", [rkAny]); changed += 1   // триггер запишет локальный tombstone
                }
                let cur = scalarStr(db, "SELECT deleted_at FROM sync_tombstones WHERE tbl=? AND row_key=?", [t, rk])
                if cur == nil || del > (cur ?? "") {
                    try db.run("INSERT OR REPLACE INTO sync_tombstones(tbl,row_key,deleted_at) VALUES(?,?,?)", [t, rk, del])
                }
            }
            // 3) union-таблицы (логи/отметки) — добавить недостающее
            for t in syncUnion {
                guard let rows = tables[t] as? [[String: Any]] else { continue }
                for row in rows {
                    if t == "metric_log", let mid = row["metric_id"], let dt = row["date"] as? String,
                       scalarStr(db, "SELECT deleted_at FROM sync_tombstones WHERE tbl = 'metric_log' AND row_key = ?", ["\(intval(mid))|\(dt)"]) != nil {
                        continue   // запись метрики удалена на этом устройстве → не возвращаем из синка
                    }
                    let cols = knownKeys(db, t, row); guard !cols.isEmpty else { continue }
                    let colList = cols.map { "\"\($0)\"" }.joined(separator: ",")
                    let marks = cols.map { _ in "?" }.joined(separator: ",")
                    let vals: [Any?] = cols.map { c in let v = row[c]; return (v is NSNull) ? nil : v }
                    try db.run("INSERT OR IGNORE INTO \(t)(\(colList)) VALUES(\(marks))", vals); changed += db.changes()
                }
            }
            try rebuildFTS(db)
            try db.run("COMMIT")
        } catch {
            _ = try? db.run("ROLLBACK")
            throw error
        }
        if changed > 0 { dedupePractices(db); dedupeTreeItems(db, "portfolio_items", nil); dedupeTreeItems(db, "target_items", "target_moves") }   // свести дубли практик, факта и целевого, принесённые синхроном (разные id)
        // фронт принимаем ТОЛЬКО от уже доверенного устройства: не давать незнакомому пиру
        // в окне первой связки подменить веб-интерфейс (= исполнение кода в WebView)
        if applyWeb, let web = snapshot["web"] as? [String: String], !web.isEmpty { try? applyFrontend(web) }
        return changed
    }

    // Вставка/обновление строки целиком из словаря (updated_at берём из строки, чтобы
    // НЕ сработал touch-триггер и сохранилось время отправителя).
    // Реальные колонки таблицы (кэш). Имя таблицы — из жёстких списков syncKeyed/syncUnion/syncTables,
    // не из входящих данных, поэтому интерполяция в PRAGMA безопасна.
    private static var colCache: [String: Set<String>] = [:]
    private static func tableColumns(_ db: Database, _ t: String) -> Set<String> {
        if let c = colCache[t] { return c }
        let names = (try? db.rows("PRAGMA table_info(\(t))"))?.compactMap { $0["name"] as? String } ?? []
        let set = Set(names)
        if !set.isEmpty { colCache[t] = set }
        return set
    }
    // Отбрасываем пришедшие от пира колонки, которых нет в нашей схеме (битая/другой версии строка
    // не должна валить всю транзакцию слияния; неизвестные поля просто игнорируем).
    private static func knownKeys(_ db: Database, _ t: String, _ row: [String: Any]) -> [String] {
        let known = tableColumns(db, t)
        let cols = Array(row.keys)
        return known.isEmpty ? cols : cols.filter { known.contains($0) }
    }

    private static func upsertRow(_ db: Database, _ t: String, _ row: [String: Any], replaceKey: Bool?, keyCol: String, rk: Any) throws {
        var r = row
        if r["updated_at"] == nil || r["updated_at"] is NSNull { r["updated_at"] = isoNow() }
        let cols = knownKeys(db, t, r); guard !cols.isEmpty, cols.contains(keyCol) else { return }
        let vals: [Any?] = cols.map { c in let v = r[c]; return (v is NSNull) ? nil : v }
        if replaceKey == true {
            // ПОЛЕВОЕ слияние: входящее ПУСТОЕ (NULL / пустая строка) НЕ затирает заполненное локально.
            // Иначе правка одного поля на одном устройстве стирала бы поля, заполненные только на другом
            // (так терялись валюты в портфеле, суммы/названия расходов). Числовой 0 пустым НЕ считается.
            let local = (try? db.rows("SELECT * FROM \(t) WHERE \(keyCol) = ?", [rk]))?.first ?? [:]
            // пустое: NULL/'' и «пустые» JSON-контейнеры ('[]'/'{}') — иначе пустой дневник ('[]' в answers)
            // или пустые steps с одного устройства затирали заполненный текст на другом
            func empty(_ v: Any?) -> Bool {
                if v == nil || v is NSNull { return true }
                if let s = (v as? String)?.trimmingCharacters(in: .whitespaces) { return s.isEmpty || s == "[]" || s == "{}" }
                return false
            }
            var setCols: [String] = []; var setVals: [Any?] = []
            for c in cols where c != keyCol {
                let inV = r[c]
                if empty(inV) && !empty(local[c]) { continue }   // не затираем заполненное пустым
                setCols.append(c); setVals.append(inV is NSNull ? nil : inV)
            }
            guard !setCols.isEmpty else { return }
            let sets = setCols.map { "\"\($0)\" = ?" }.joined(separator: ", ")
            try db.run("UPDATE \(t) SET \(sets) WHERE \(keyCol) = ?", setVals + [rk])
        } else {
            let colList = cols.map { "\"\($0)\"" }.joined(separator: ",")
            let marks = cols.map { _ in "?" }.joined(separator: ",")
            try db.run("INSERT INTO \(t)(\(colList)) VALUES(\(marks))", vals)
        }
    }

    private static func scalarStr(_ db: Database, _ sql: String, _ params: [Any?]) -> String? {
        (try? db.rows(sql, params))?.first?.values.first as? String
    }

    private static func existsRow(_ db: Database, _ t: String, _ key: String, _ rk: Any) -> Bool {
        ((try? db.rows("SELECT 1 AS x FROM \(t) WHERE \(key) = ? LIMIT 1", [rk]))?.isEmpty == false)
    }

    private static func rebuildFTS(_ db: Database) throws {
        try db.run("DELETE FROM node_fts")
        for n in try db.rows("SELECT id, title, note FROM nodes") {
            try db.run("INSERT INTO node_fts(rowid, title_norm, note_norm) VALUES(?,?,?)",
                       [n["id"], norm(n["title"] as? String ?? ""), norm(n["note"] as? String ?? "")])
        }
        try db.run("DELETE FROM page_fts")
        for p in try db.rows("SELECT id, title, content FROM pages") {
            try db.run("INSERT INTO page_fts(rowid, title_norm, content_norm) VALUES(?,?,?)",
                       [p["id"], norm(p["title"] as? String ?? ""), norm(p["content"] as? String ?? "")])
        }
    }

    private static func isoNow() -> String {
        let f = DateFormatter(); f.dateFormat = "yyyy-MM-dd HH:mm:ss"
        f.locale = Locale(identifier: "en_US_POSIX"); return f.string(from: Date())
    }
}

// Постоянная пара устройств: устойчивый identity-ключ (X25519) + доверенный пир.
// Хранится локально (UserDefaults) — НЕ синхронизируется. После первой сверки кода
// пир запоминается, и дальше авто-синхрон идёт без кода.
enum SyncTrust {
    private static let idKey = "pipboy.sync.identity"
    private static let peerKey = "pipboy.sync.peer"
    private static let autoKey = "pipboy.sync.auto"

    static func identity() -> Curve25519.KeyAgreement.PrivateKey {
        let d = UserDefaults.standard
        if let b64 = d.string(forKey: idKey), let raw = Data(base64Encoded: b64),
           let k = try? Curve25519.KeyAgreement.PrivateKey(rawRepresentation: raw) { return k }
        let k = Curve25519.KeyAgreement.PrivateKey()
        d.set(k.rawRepresentation.base64EncodedString(), forKey: idKey)
        return k
    }
    static var trustedPeer: Data? {
        get { UserDefaults.standard.string(forKey: peerKey).flatMap { Data(base64Encoded: $0) } }
        set {
            if let v = newValue { UserDefaults.standard.set(v.base64EncodedString(), forKey: peerKey) }
            else { UserDefaults.standard.removeObject(forKey: peerKey) }
        }
    }
    static func isTrusted(_ pub: Data) -> Bool { trustedPeer == pub }
    static var paired: Bool { trustedPeer != nil }
    static var autoEnabled: Bool {
        get { UserDefaults.standard.object(forKey: autoKey) == nil ? true : UserDefaults.standard.bool(forKey: autoKey) }
        set { UserDefaults.standard.set(newValue, forKey: autoKey) }
    }
}


// ===== Транспорт синхронизации по локальной сети (этап 1: Mac → iPhone) =====
// host (обычно Mac): объявляет Bonjour _pipboy._tcp и на подключение шлёт снимок базы.
// receive (обычно iPhone): находит сервис, подключается, принимает снимок и заменяет
// им свои данные. Канал — эфемерный X25519 (ECDH) + AES-GCM; 6-значный код (SAS)
// выводится на обоих для визуальной сверки против MITM. Без TLS-сертификатов и паролей.
// Внимание: требует ключей Info.plist (NSLocalNetworkUsageDescription, NSBonjourServices)
// и разрешения «локальная сеть» на iPhone при первом запуске.
final class SyncService: ObservableObject {
    static let serviceType = "_pipboy._tcp"
    enum Role { case host, client }

    @Published var status = ""              // для нативной панели (SwiftUI)
    @Published var sas = ""                 // 6-значный код сверки (одинаков на обоих)
    @Published var appliedCount = 0         // ++ после применения снимка → перезагрузка WebView
    var onStatus: ((String) -> Void)?       // зеркало статуса в веб-карточку (Mac)
    var onSas: ((String) -> Void)?          // показать код сверки + кнопки «совпадает/нет» в вебе
    var onSasClear: (() -> Void)?           // спрятать блок сверки кода

    private var listener: NWListener?
    private var browser: NWBrowser?
    private var connection: NWConnection?
    private let priv = SyncTrust.identity()   // постоянный identity-ключ (пара устройств)
    private var browseRetries = 0
    private var pendingPeer: Data?            // pub-ключ пира текущего обмена → запомнить при успехе
    private var busy = false                  // идёт обмен — не запускать второй параллельно
    private var lastDone = Date.distantPast   // антидребезг авто-синхрона
    private var autoMode = false              // авто-обмен: только с уже доверенным пиром, без кода
    private var autoTimer: Timer?
    private var watchdog: Timer?              // обрывает зависший обмен, чтобы busy не залип навсегда
    private var confirmCont: ((Bool) -> Void)?   // продолжение гейта сверки кода (ждёт «совпадает/нет»)
    private var bgCompletion: ((Bool) -> Void)?  // колбэк завершения для фоновой задачи (BGAppRefreshTask)

    static weak var shared: SyncService?      // ссылка для фоновой задачи (один экземпляр в приложении)
    init() { SyncService.shared = self }

    // Один проход синхрона для «мягкого фона»: как autoSyncNow, но с колбэком завершения.
    // Вызывается из BGAppRefreshTask только когда ключ базы ещё в памяти.
    func backgroundSyncOnce(_ completion: @escaping (Bool) -> Void) {
        guard SyncTrust.paired, SyncTrust.autoEnabled, !busy else { completion(false); return }
        bgCompletion = completion
        autoMode = true; browseRetries = 0
        startBrowse()
    }

    // ----- раздать данные (источник) -----
    func host(auto: Bool = false) {
        autoMode = auto
        stop(); say("поднимаю раздачу…")
        do {
            let params = NWParameters.tcp
            params.includePeerToPeer = true
            let l = try NWListener(using: params)
            l.service = NWListener.Service(name: "Pipboy", type: Self.serviceType)
            l.newConnectionHandler = { [weak self] conn in
                guard let self else { return }
                if self.busy || self.connection != nil { conn.cancel(); return }   // одно подключение за раз
                self.connection = conn
                self.begin(conn, role: .host)
            }
            l.stateUpdateHandler = { [weak self] st in
                guard let self else { return }
                switch st {
                case .ready: self.say(SyncTrust.paired ? "✅ авто-раздача · жду iPhone" : "✅ раздаю · открой «Получить» на iPhone и сверь код")
                case .waiting(let e): self.say("⏳ жду сеть (\(Self.human(e))) · разреши «локальную сеть», если спросит")
                case .failed(let e): self.say("ошибка хоста: \(Self.human(e))")
                default: break
                }
            }
            l.start(queue: .main)
            listener = l
        } catch { say("не удалось поднять хост: \(error)") }
    }

    // ===== Авто-синхрон: Mac постоянно раздаёт, iPhone синхронится при открытии =====
    func autoStart() {
        guard SyncTrust.paired, SyncTrust.autoEnabled else { return }
        #if os(macOS)
        host(auto: true)                     // слушаем постоянно, пере-принимаем после каждого обмена
        #else
        autoSyncNow()
        autoTimer?.invalidate()
        autoTimer = Timer.scheduledTimer(withTimeInterval: 120, repeats: true) { [weak self] _ in self?.autoSyncNow() }
        #endif
    }
    func autoStop() { autoTimer?.invalidate(); autoTimer = nil; stop() }
    // Сбросить пару: следующий синхрон снова потребует сверки кода (смена/потеря устройства, тест).
    func unpair() {
        SyncTrust.trustedPeer = nil
        autoStop()
        say("пара сброшена — при следующей связке сверишь код заново")
    }
    private func autoSyncNow() {
        guard SyncTrust.paired, SyncTrust.autoEnabled, !busy, Date().timeIntervalSince(lastDone) > 15 else { return }
        autoMode = true; browseRetries = 0; startBrowse()
    }

    // ----- получить данные (приёмник) -----
    func receive() { autoMode = false; browseRetries = 0; startBrowse() }

    private func startBrowse() {
        stop(); say("ищу Mac в той же Wi-Fi…")
        let params = NWParameters.tcp
        params.includePeerToPeer = true
        let b = NWBrowser(for: .bonjour(type: Self.serviceType, domain: nil), using: params)
        b.browseResultsChangedHandler = { [weak self] results, _ in
            guard let self, self.connection == nil, let first = results.first else { return }
            self.say("нашёл Mac · соединяюсь…")
            let conn = NWConnection(to: first.endpoint, using: params)
            self.connection = conn
            self.begin(conn, role: .client)
        }
        b.stateUpdateHandler = { [weak self] st in
            guard let self else { return }
            switch st {
            case .ready: self.say("ищу Mac… (на Mac должно быть нажато «раздать»)")
            case .waiting(let e): self.handleBrowseIssue(e)
            case .failed(let e): self.handleBrowseIssue(e)
            default: break
            }
        }
        b.start(queue: .main)
        browser = b
    }

    // -65555 NoAuth / -65570 PolicyDenied: первый запрос вызывает системный диалог
    // «локальной сети» и падает — повторяем после того, как пользователь разрешит.
    private func handleBrowseIssue(_ e: NWError) {
        if Self.isLocalNetworkDenied(e) {
            if browseRetries < 5 {
                browseRetries += 1
                say("разреши доступ к локальной сети · повторяю \(browseRetries)/5…")
                DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { [weak self] in self?.startBrowse() }
            } else {
                say("нет доступа к локальной сети. Настройки → Приватность → Локальная сеть → включи Pipboy, потом «Получить»")
            }
        } else {
            say("поиск: \(Self.human(e))")
        }
    }

    private static func isLocalNetworkDenied(_ e: NWError) -> Bool {
        if case let .dns(code) = e { return code == -65555 || code == -65570 }
        return false
    }

    static func human(_ e: NWError) -> String {
        if case let .dns(code) = e {
            if code == -65555 || code == -65570 { return "нет доступа к локальной сети" }
            return "dns \(code)"
        }
        return "\(e)"
    }

    func stop() {
        watchdog?.invalidate(); watchdog = nil
        busy = false; pendingPeer = nil; confirmCont = nil; onSasClear?()
        listener?.cancel(); listener = nil
        browser?.cancel(); browser = nil
        connection?.cancel(); connection = nil
    }

    private func say(_ s: String) { DispatchQueue.main.async { self.status = s; self.onStatus?(s) } }

    private func begin(_ conn: NWConnection, role: Role) {
        busy = true; armWatchdog(); say("соединяюсь…")
        conn.stateUpdateHandler = { [weak self] st in
            guard let self else { return }
            switch st {
            case .ready: self.handshake(conn, role: role)
            case .waiting(let e): self.say("⏳ соединение ждёт (\(Self.human(e)))…")
            case .failed(let e): self.say("соединение разорвано: \(Self.human(e))"); self.finish(ok: false)
            case .cancelled: break
            default: break
            }
        }
        conn.start(queue: .main)
    }

    // Конец обмена: снять busy; на Mac в авто-режиме — снова готов принять следующий.
    private func armWatchdog(_ secs: TimeInterval = 60) {
        watchdog?.invalidate()
        watchdog = Timer.scheduledTimer(withTimeInterval: secs, repeats: false) { [weak self] _ in
            guard let self, self.busy else { return }
            self.say("тайм-аут синхрона — обрываю"); self.finish(ok: false)
        }
    }

    private func finish(ok: Bool) {
        watchdog?.invalidate(); watchdog = nil
        busy = false
        confirmCont = nil; onSasClear?()   // снять незакрытый гейт сверки кода
        let wasPaired = SyncTrust.paired
        if ok { lastDone = Date(); if let p = pendingPeer { SyncTrust.trustedPeer = p } }   // запомнить пир
        pendingPeer = nil
        connection?.cancel(); connection = nil   // листенер в авто-режиме остаётся — примет следующий
        if let cb = bgCompletion { bgCompletion = nil; DispatchQueue.main.async { cb(ok) } }   // завершить фоновую задачу
        if ok && !wasPaired { DispatchQueue.main.async { self.autoStart() } }   // первая связка прошла → включить авто
    }

    // обмен публичными ключами → общий ключ (+ код сверки, если пир ещё не знаком)
    private func handshake(_ conn: NWConnection, role: Role) {
        say("обмен ключами…")
        send(conn, priv.publicKey.rawRepresentation) { [weak self] ok in
            guard let self, ok else { self?.say("сбой отправки ключа"); self?.finish(ok: false); return }
            self.recv(conn) { [weak self] data in
                guard let self else { return }
                guard let data,
                      let theirPub = try? Curve25519.KeyAgreement.PublicKey(rawRepresentation: data),
                      let shared = try? self.priv.sharedSecretFromKeyAgreement(with: theirPub) else {
                    self.say("не удалось согласовать ключ"); self.finish(ok: false); return
                }
                // в авто-режиме связываемся ТОЛЬКО с уже доверенным устройством (без авто-пары с чужим)
                if self.autoMode && !SyncTrust.isTrusted(data) {
                    self.say("незнакомое устройство — нужна ручная связка"); self.finish(ok: false); return
                }
                self.pendingPeer = data
                let key = shared.hkdfDerivedSymmetricKey(using: SHA256.self,
                    salt: Data("pipboy-sync".utf8), sharedInfo: Data("v1".utf8), outputByteCount: 32)
                let proceed = { [weak self] in
                    guard let self else { return }
                    if role == .host { self.hostExchange(conn, key: key) } else { self.clientExchange(conn, key: key) }
                }
                if SyncTrust.isTrusted(data) {
                    self.say("устройство знакомо · синхронизирую…")     // пара уже сверена — без кода
                    proceed()
                } else {
                    let sasKey = shared.hkdfDerivedSymmetricKey(using: SHA256.self,
                        salt: Data("pipboy-sas".utf8), sharedInfo: Data("v1".utf8), outputByteCount: 4)
                    let b = sasKey.withUnsafeBytes { Array($0) }
                    let n = (UInt32(b[0]) << 24 | UInt32(b[1]) << 16 | UInt32(b[2]) << 8 | UInt32(b[3])) % 1_000_000
                    self.sas = String(format: "%06u", n)
                    self.say("код сверки \(self.sas) — сверь и подтверди на обоих устройствах")
                    // первая связка: НИЧЕГО не отправляем, пока оба не подтвердят совпадение кода
                    self.confirmGate(conn) { [weak self] bothOk in
                        guard let self else { return }
                        if bothOk { proceed() }
                        else { self.say("связка отменена — код не подтверждён"); self.finish(ok: false) }
                    }
                }
            }
        }
    }

    // Гейт первой связки (anti-MITM): показываем код, ждём ЛОКАЛЬНОГО «совпадает», обмениваемся
    // решениями (1 байт) и продолжаем ТОЛЬКО если подтвердили обе стороны. До этого снимок не
    // покидает устройство и пир не запоминается. Окно сверки шире — перезапускаем watchdog.
    private func confirmGate(_ conn: NWConnection, _ done: @escaping (Bool) -> Void) {
        armWatchdog(180)
        DispatchQueue.main.async {
            self.onSas?(self.sas)
            self.confirmCont = { [weak self] localOk in
                guard let self else { done(false); return }
                self.onSasClear?()
                self.send(conn, Data([localOk ? 1 : 0])) { sent in
                    guard sent else { done(false); return }
                    self.say(localOk ? "жду подтверждения на втором устройстве…" : "отменяю…")
                    self.recv(conn) { data in
                        let peerOk = (data?.first == 1)
                        done(localOk && peerOk)
                    }
                }
            }
        }
    }

    // Веб/нативная панель прислала результат сверки кода.
    func confirmSas(_ ok: Bool) {
        let c = confirmCont; confirmCont = nil
        if c == nil { return }   // нет активного гейта — игнор
        c?(ok)
    }

    // Двусторонний обмен: обе стороны шлют снимок и сливают встречный (LWW + tombstones).
    // host: отправляет своё → ждёт встречное → merge. client: принимает → merge → шлёт своё.
    private func hostExchange(_ conn: NWConnection, key: SymmetricKey) {
        say("готовлю снимок…")
        DispatchQueue.global().async {
            do {
                let sealed = try self.sealedSnapshot(key)
                DispatchQueue.main.async {
                    self.say("отправляю данные…")
                    self.send(conn, sealed) { ok in
                        guard ok else { self.say("сбой отправки"); self.finish(ok: false); return }
                        self.say("жду изменения со второго устройства…")
                        self.recv(conn) { data in
                            guard let data else { self.say("нет ответа"); self.finish(ok: false); return }
                            self.mergeIncoming(data, key: key) { ok in
                                if ok { self.say("синхронизировано ✓\(SyncTrust.paired ? "" : " · код \(self.sas)")") }
                                self.finish(ok: ok)
                            }
                        }
                    }
                }
            } catch { self.say("ошибка снимка: \(error)"); self.finish(ok: false) }
        }
    }

    private func clientExchange(_ conn: NWConnection, key: SymmetricKey) {
        say("принимаю данные…")
        recv(conn) { data in
            guard let data else { self.say("нет данных"); self.finish(ok: false); return }
            self.mergeIncoming(data, key: key) { merged in
                guard merged else { self.finish(ok: false); return }
                DispatchQueue.global().async {
                    do {
                        let sealed = try self.sealedSnapshot(key)   // своё (уже после слияния) — хосту
                        DispatchQueue.main.async {
                            self.say("отправляю свои изменения…")
                            self.send(conn, sealed) { ok in
                                self.say(ok ? "синхронизировано ✓\(SyncTrust.paired ? "" : " · код \(self.sas)")" : "сбой отправки")
                                self.finish(ok: ok)
                            }
                        }
                    } catch { self.say("ошибка снимка: \(error)"); self.finish(ok: false) }
                }
            }
        }
    }

    private func sealedSnapshot(_ key: SymmetricKey) throws -> Data {
        guard let k = KeyHolder.shared.key else { throw Database.Failure.open(0) }
        let snap = try Api.syncSnapshot(try Database(key: k))
        let plain = try JSONSerialization.data(withJSONObject: snap)
        guard let sealed = try AES.GCM.seal(plain, using: key).combined else { throw Api.Unsupported(path: "seal") }
        return sealed
    }

    private func mergeIncoming(_ data: Data, key: SymmetricKey, then: @escaping (Bool) -> Void) {
        DispatchQueue.global().async {
            do {
                let plain = try AES.GCM.open(try AES.GCM.SealedBox(combined: data), using: key)
                guard let snap = try JSONSerialization.jsonObject(with: plain) as? [String: Any] else {
                    throw Api.Unsupported(path: "плохой снимок") }
                guard let k = KeyHolder.shared.key else { throw Database.Failure.open(0) }
                // фронт берём только от уже доверенного пира (после первой сверки кода)
                let trusted = SyncTrust.isTrusted(self.pendingPeer ?? Data())
                let changed = try Api.syncApplyMerge(try Database(key: k), snap, applyWeb: trusted)
                // дёргаем экран ТОЛЬКО если реально что-то изменилось (иначе фоновый синхрон незаметен)
                DispatchQueue.main.async { if changed > 0 { self.appliedCount += 1 }; then(true) }
            } catch {
                DispatchQueue.main.async { self.say("ошибка применения: \(error)"); then(false) }
            }
        }
    }

    // ----- кадрирование: UInt32 BE длина + полезная нагрузка -----
    private func send(_ conn: NWConnection, _ payload: Data, done: @escaping (Bool) -> Void) {
        let n = UInt32(payload.count)
        var frame = Data([UInt8(n >> 24 & 0xff), UInt8(n >> 16 & 0xff), UInt8(n >> 8 & 0xff), UInt8(n & 0xff)])
        frame.append(payload)
        conn.send(content: frame, completion: .contentProcessed { err in
            DispatchQueue.main.async { done(err == nil) } })
    }

    private static let maxFrame = 256 * 1024 * 1024   // потолок кадра: персональный снимок сильно меньше; защита от OOM-кадра от пира в сети

    private func recv(_ conn: NWConnection, done: @escaping (Data?) -> Void) {
        conn.receive(minimumIncompleteLength: 4, maximumLength: 4) { hdr, _, _, err in
            guard let hdr, hdr.count == 4, err == nil else { DispatchQueue.main.async { done(nil) }; return }
            let n = hdr.reduce(0) { ($0 << 8) | Int($1) }
            guard n >= 0, n <= Self.maxFrame else { DispatchQueue.main.async { done(nil) }; return }   // заявлена несуразная длина → рвём
            self.recvExactly(conn, n, Data(), done)
        }
    }

    private func recvExactly(_ conn: NWConnection, _ remaining: Int, _ acc: Data, _ done: @escaping (Data?) -> Void) {
        if remaining <= 0 { DispatchQueue.main.async { done(acc) }; return }
        conn.receive(minimumIncompleteLength: 1, maximumLength: remaining) { part, _, _, err in
            guard let part, !part.isEmpty, err == nil else { DispatchQueue.main.async { done(nil) }; return }
            var next = acc; next.append(part)
            self.recvExactly(conn, remaining - part.count, next, done)
        }
    }
}
