import Foundation
#if canImport(SQLCipher)
import SQLCipher
#else
import SQLite3
#endif

// Зашифрованная база (SQLCipher). Ключ — из Keychain под Touch ID.
// Тонкая обёртка над C-API sqlite3: на неё будут ложиться SQL-строки из server.js.
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

    // Замок включён, если в settings есть непустой lock_pw_hash.
    func lockEnabled() throws -> Bool {
        if let v = try rows("SELECT value FROM settings WHERE key = 'lock_pw_hash'").first?["value"] as? String {
            return !v.isEmpty
        }
        return false
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
