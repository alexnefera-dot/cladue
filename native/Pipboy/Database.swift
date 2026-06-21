import Foundation
#if canImport(SQLCipher)
import SQLCipher
#else
import SQLite3
#endif

// Зашифрованная база (SQLCipher). Ключ — из Keychain под Touch ID.
// Тонкая обёртка над C-API sqlite3 (на неё легли SQL-запросы нативного слоя).
final class Database {
    enum Failure: Error { case open(Int32), sql(String) }

    // true, если в сборку реально вкомпилён SQLCipher (продукт привязан к таргету).
    // Если false — используется системный SQLite БЕЗ шифрования (PRAGMA key молчит).
    static let sqlcipherActive: Bool = {
        #if canImport(SQLCipher)
        return true
        #else
        return false
        #endif
    }()

    private var handle: OpaquePointer?

    init(key: Data) throws {
        let url = try Database.fileURL()
        let flags = SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE
        guard sqlite3_open_v2(url.path, &handle, flags, nil) == SQLITE_OK else {
            let code = sqlite3_errcode(handle)
            sqlite3_close(handle); handle = nil
            throw Failure.open(code)
        }
        // SQLCipher: задаём raw-ключ (hex) ДО первого обращения к данным.
        let hex = key.map { String(format: "%02x", $0) }.joined()
        try exec("PRAGMA key = \"x'\(hex)'\"")
        try exec("PRAGMA foreign_keys = ON")
        try exec("PRAGMA busy_timeout = 5000")   // во время слияния второе соединение ждёт, а не падает с BUSY
        // Первое чтение служебной таблицы расшифрует заголовок — проверка ключа.
        try exec("SELECT count(*) FROM sqlite_master")
    }

    deinit { if handle != nil { sqlite3_close(handle) } }

    // Выполнить SQL без результата (DDL/DML).
    func exec(_ sql: String) throws {
        var err: UnsafeMutablePointer<CChar>?
        if sqlite3_exec(handle, sql, nil, nil, &err) != SQLITE_OK {
            let msg = err.map { String(cString: $0) } ?? "unknown"
            sqlite3_free(err)
            throw Failure.sql(msg)
        }
    }

    // Одно целое из первого столбца первой строки.
    func scalarInt(_ sql: String) throws -> Int {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(handle, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw Failure.sql(String(cString: sqlite3_errmsg(handle)))
        }
        defer { sqlite3_finalize(stmt) }
        return sqlite3_step(stmt) == SQLITE_ROW ? Int(sqlite3_column_int64(stmt, 0)) : 0
    }

    private func bind(_ stmt: OpaquePointer?, _ params: [Any?]) {
        let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
        for (i, p) in params.enumerated() {
            let idx = Int32(i + 1)
            switch p {
            case nil, is NSNull:        sqlite3_bind_null(stmt, idx)
            case let v as Bool:         sqlite3_bind_int64(stmt, idx, v ? 1 : 0)
            case let v as Int:          sqlite3_bind_int64(stmt, idx, Int64(v))
            case let v as Double:       sqlite3_bind_double(stmt, idx, v)
            case let v as String:       sqlite3_bind_text(stmt, idx, v, -1, transient)
            default:                    sqlite3_bind_text(stmt, idx, "\(p!)", -1, transient)
            }
        }
    }

    // INSERT/UPDATE/DELETE; возвращает last_insert_rowid (для INSERT).
    @discardableResult
    func run(_ sql: String, _ params: [Any?] = []) throws -> Int {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(handle, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw Failure.sql(String(cString: sqlite3_errmsg(handle)))
        }
        defer { sqlite3_finalize(stmt) }
        bind(stmt, params)
        guard sqlite3_step(stmt) == SQLITE_DONE else {
            throw Failure.sql(String(cString: sqlite3_errmsg(handle)))
        }
        return Int(sqlite3_last_insert_rowid(handle))
    }

    // Строки запроса как массив словарей (как node:sqlite .all()).
    func rows(_ sql: String, _ params: [Any?] = []) throws -> [[String: Any]] {
        var stmt: OpaquePointer?
        guard sqlite3_prepare_v2(handle, sql, -1, &stmt, nil) == SQLITE_OK else {
            throw Failure.sql(String(cString: sqlite3_errmsg(handle)))
        }
        defer { sqlite3_finalize(stmt) }
        bind(stmt, params)
        var out: [[String: Any]] = []
        let cols = sqlite3_column_count(stmt)
        while sqlite3_step(stmt) == SQLITE_ROW {
            var row: [String: Any] = [:]
            for c in 0..<cols {
                let name = String(cString: sqlite3_column_name(stmt, c))
                switch sqlite3_column_type(stmt, c) {
                case SQLITE_INTEGER: row[name] = Int(sqlite3_column_int64(stmt, c))
                case SQLITE_FLOAT:   row[name] = sqlite3_column_double(stmt, c)
                case SQLITE_NULL:    row[name] = NSNull()
                default:
                    if let t = sqlite3_column_text(stmt, c) { row[name] = String(cString: t) }
                    else { row[name] = NSNull() }
                }
            }
            out.append(row)
        }
        return out
    }

    // Число строк, затронутых последним INSERT/UPDATE/DELETE.
    func changes() -> Int { Int(sqlite3_changes(handle)) }

    // Замок включён, если в settings есть непустой lock_pw_hash.
    func lockEnabled() throws -> Bool {
        if let v = try rows("SELECT value FROM settings WHERE key = 'lock_pw_hash'").first?["value"] as? String {
            return !v.isEmpty
        }
        return false
    }

    // Полная схема (порт app/db.js). На Mac таблицы приезжают импортом data.db
    // (sqlcipher_export), но на iOS/чистом Mac база пустая — без этого ни сид, ни
    // запросы не работают (каждый экран пустой). Колонки-миграции вложены прямо в
    // CREATE (итоговая форма). Идемпотентно: CREATE TABLE IF NOT EXISTS.
    func ensureSchema() throws {
        try exec("""
        CREATE TABLE IF NOT EXISTS nodes(
          id INTEGER PRIMARY KEY,
          parent_id INTEGER REFERENCES nodes(id) ON DELETE CASCADE,
          ord INTEGER NOT NULL,
          title TEXT NOT NULL,
          note TEXT NOT NULL DEFAULT '',
          is_category INTEGER NOT NULL DEFAULT 0,
          kind TEXT, status TEXT, priority TEXT, due_date TEXT,
          answer TEXT, "repeat" TEXT, due_time TEXT,
          created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
          completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS links(
          id INTEGER PRIMARY KEY,
          from_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
          to_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
          type TEXT NOT NULL DEFAULT 'related',
          UNIQUE(from_id, to_id, type)
        );
        CREATE TABLE IF NOT EXISTS dismissed(a INTEGER NOT NULL, b INTEGER NOT NULL, UNIQUE(a, b));
        CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(title_norm, note_norm);
        CREATE TABLE IF NOT EXISTS accounts(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL,
          type TEXT NOT NULL DEFAULT 'bank', currency TEXT NOT NULL DEFAULT '€',
          balance REAL NOT NULL DEFAULT 0,
          balance_updated_at TEXT NOT NULL DEFAULT (datetime('now')),
          note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS portfolio_classes(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL,
          value REAL NOT NULL DEFAULT 0, target_pct REAL NOT NULL DEFAULT 0,
          ord INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS steps(
          id INTEGER PRIMARY KEY, kind TEXT NOT NULL DEFAULT 'buy',
          title TEXT NOT NULL, amount REAL, planned_date TEXT,
          condition TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'planned',
          note TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')),
          task_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS obligations(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0,
          currency TEXT NOT NULL DEFAULT '€', period TEXT NOT NULL DEFAULT 'monthly',
          next_date TEXT, remind_days INTEGER NOT NULL DEFAULT 5,
          kind TEXT NOT NULL DEFAULT 'liability', note TEXT NOT NULL DEFAULT '',
          property_id INTEGER
        );
        CREATE TABLE IF NOT EXISTS portfolio_items(
          id INTEGER PRIMARY KEY,
          parent_id INTEGER REFERENCES portfolio_items(id) ON DELETE CASCADE,
          ord INTEGER NOT NULL DEFAULT 0, name TEXT NOT NULL,
          kind TEXT NOT NULL DEFAULT 'asset', buy_value REAL, value REAL,
          target_value REAL, note TEXT NOT NULL DEFAULT '',
          currency TEXT NOT NULL DEFAULT '€', is_loan INTEGER NOT NULL DEFAULT 0,
          loan_due TEXT, asset_type TEXT, qty REAL, rate_symbol TEXT
        );
        CREATE TABLE IF NOT EXISTS rates(
          symbol TEXT PRIMARY KEY, label TEXT, price REAL, change_pct REAL, updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS events(
          id INTEGER PRIMARY KEY, title TEXT NOT NULL, date TEXT NOT NULL, time TEXT,
          recur TEXT NOT NULL DEFAULT 'none', note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS event_done(
          event_id INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
          date TEXT NOT NULL, UNIQUE(event_id, date)
        );
        CREATE TABLE IF NOT EXISTS transactions(
          id INTEGER PRIMARY KEY, date TEXT NOT NULL, amount REAL NOT NULL,
          currency TEXT NOT NULL DEFAULT '€', direction TEXT NOT NULL DEFAULT 'expense',
          category TEXT NOT NULL DEFAULT 'прочее', note TEXT NOT NULL DEFAULT '',
          source TEXT NOT NULL DEFAULT 'manual'
        );
        CREATE TABLE IF NOT EXISTS receivables(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, amount REAL NOT NULL,
          currency TEXT NOT NULL DEFAULT '€', expected_date TEXT,
          status TEXT NOT NULL DEFAULT 'waiting', note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS passive_income(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0,
          currency TEXT NOT NULL DEFAULT '€', period TEXT NOT NULL DEFAULT 'monthly',
          next_date TEXT, note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS macro_notes(
          id INTEGER PRIMARY KEY, date TEXT NOT NULL DEFAULT (date('now')),
          phase TEXT NOT NULL DEFAULT '', thesis TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS debts(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, amount REAL NOT NULL DEFAULT 0,
          currency TEXT NOT NULL DEFAULT '€', direction TEXT NOT NULL DEFAULT 'owed_to_me',
          due_date TEXT, note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS snapshots(date TEXT PRIMARY KEY, portfolio_eur REAL);
        CREATE TABLE IF NOT EXISTS routines(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, slot TEXT NOT NULL DEFAULT 'утро',
          ord INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
          planned INTEGER NOT NULL DEFAULT 0, time TEXT, days TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS routine_log(
          routine_id INTEGER NOT NULL REFERENCES routines(id) ON DELETE CASCADE,
          date TEXT NOT NULL, UNIQUE(routine_id, date)
        );
        CREATE TABLE IF NOT EXISTS people(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, birthday TEXT,
          rhythm_days INTEGER, last_contact TEXT, note TEXT NOT NULL DEFAULT '',
          tags TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS contact_log(
          id INTEGER PRIMARY KEY,
          person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
          date TEXT NOT NULL DEFAULT (date('now')), note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS pages(
          id INTEGER PRIMARY KEY,
          parent_id INTEGER REFERENCES pages(id) ON DELETE CASCADE,
          ord INTEGER NOT NULL DEFAULT 0, title TEXT NOT NULL,
          content TEXT NOT NULL DEFAULT '', node_id INTEGER,
          created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
          updated_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
          locked INTEGER NOT NULL DEFAULT 0, enc TEXT
        );
        CREATE TABLE IF NOT EXISTS page_revisions(
          id INTEGER PRIMARY KEY,
          page_id INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
          content TEXT NOT NULL, saved_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(title_norm, content_norm);
        CREATE TABLE IF NOT EXISTS attachments(
          id INTEGER PRIMARY KEY,
          page_id INTEGER REFERENCES pages(id) ON DELETE CASCADE,
          name TEXT NOT NULL DEFAULT '', mime TEXT NOT NULL DEFAULT 'application/octet-stream',
          data TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS practices(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'schedule',
          days TEXT NOT NULL DEFAULT '', time TEXT, steps TEXT NOT NULL DEFAULT '[]',
          note TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '', ord INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS practice_log(
          id INTEGER PRIMARY KEY,
          practice_id INTEGER NOT NULL REFERENCES practices(id) ON DELETE CASCADE,
          date TEXT NOT NULL DEFAULT (date('now')), note TEXT NOT NULL DEFAULT '',
          answers TEXT NOT NULL DEFAULT '[]'
        );
        CREATE TABLE IF NOT EXISTS wheel_areas(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, ord INTEGER NOT NULL DEFAULT 0,
          ideal TEXT NOT NULL DEFAULT '', current_desc TEXT NOT NULL DEFAULT '',
          next_desc TEXT NOT NULL DEFAULT '', step TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS wheel_scores(
          id INTEGER PRIMARY KEY, date TEXT NOT NULL,
          area_id INTEGER NOT NULL REFERENCES wheel_areas(id) ON DELETE CASCADE,
          score INTEGER NOT NULL, UNIQUE(date, area_id)
        );
        CREATE TABLE IF NOT EXISTS area_milestones(
          id INTEGER PRIMARY KEY,
          area_id INTEGER NOT NULL REFERENCES wheel_areas(id) ON DELETE CASCADE,
          level INTEGER NOT NULL DEFAULT 5, title TEXT NOT NULL DEFAULT '',
          progress INTEGER NOT NULL DEFAULT 0,
          ord INTEGER NOT NULL DEFAULT 0,
          completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS area_questions(
          id INTEGER PRIMARY KEY,
          area_id INTEGER NOT NULL REFERENCES wheel_areas(id) ON DELETE CASCADE,
          question TEXT NOT NULL DEFAULT '', answer TEXT NOT NULL DEFAULT '',
          node_id INTEGER REFERENCES nodes(id) ON DELETE SET NULL,
          metric_id INTEGER REFERENCES metrics(id) ON DELETE SET NULL,
          ord INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS work_log(
          id INTEGER PRIMARY KEY, date TEXT NOT NULL DEFAULT (date('now')),
          note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS forecasts(
          id INTEGER PRIMARY KEY, statement TEXT NOT NULL, confidence INTEGER NOT NULL,
          due_date TEXT, outcome INTEGER,
          created_at TEXT NOT NULL DEFAULT (date('now')), resolved_at TEXT
        );
        CREATE TABLE IF NOT EXISTS properties(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL,
          category TEXT NOT NULL DEFAULT 'прочее', note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS checkins(
          date TEXT PRIMARY KEY, mood INTEGER NOT NULL, note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS metrics(
          id INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL DEFAULT 'number',
          unit TEXT NOT NULL DEFAULT '', ord INTEGER NOT NULL DEFAULT 0,
          polarity TEXT NOT NULL DEFAULT 'plus', target REAL,
          cadence TEXT NOT NULL DEFAULT 'daily', source TEXT
        );
        CREATE TABLE IF NOT EXISTS metric_log(
          metric_id INTEGER NOT NULL REFERENCES metrics(id) ON DELETE CASCADE,
          date TEXT NOT NULL, value REAL NOT NULL, UNIQUE(metric_id, date)
        );
        CREATE TABLE IF NOT EXISTS node_log(
          id INTEGER PRIMARY KEY,
          node_id INTEGER NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
          date TEXT NOT NULL DEFAULT (date('now')), note TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS trash(
          id INTEGER PRIMARY KEY, kind TEXT NOT NULL, label TEXT NOT NULL,
          payload TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """)
    }

    // Этап 0a: дымовая проверка, что зашифрованная база живая.
    func smokeTest() throws -> Int {
        try exec("CREATE TABLE IF NOT EXISTS _smoke(id INTEGER PRIMARY KEY, at TEXT)")
        try exec("INSERT INTO _smoke(at) VALUES (datetime('now'))")
        return try scalarInt("SELECT COUNT(*) FROM _smoke")
    }

    // Файл в Application Support (вне репозитория, под защитой ОС).
    static func fileURL() throws -> URL {
        let dir = try FileManager.default.url(
            for: .applicationSupportDirectory, in: .userDomainMask,
            appropriateFor: nil, create: true
        ).appendingPathComponent("Pipboy", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("pipboy.db")
    }
}
