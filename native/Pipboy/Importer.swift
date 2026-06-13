import Foundation
#if canImport(SQLCipher)
import SQLCipher
#else
import SQLite3
#endif

// Разовый импорт текущей НЕзашифрованной app/data.db в зашифрованную базу.
// Приём SQLCipher: открыть плоскую базу, ATTACH зашифрованной ключом и одной
// командой `SELECT sqlcipher_export('enc')` перелить всю схему и данные в шифр.
enum Importer {
    enum Failure: Error { case sql(String) }

    static func importIfNeeded(encryptedKey key: Data) {
        do {
            let target = try Database.fileURL()
            if try alreadyImported(key: key) {
                return                                  // данные уже в зашифрованной базе
            }
            guard let source = plaintextSourceURL(),
                  FileManager.default.fileExists(atPath: source.path) else {
                NSLog("Pipboy 0b: data.db не найдена — чистый старт, импорт не нужен")
                return
            }
            try export(from: source, to: target, key: key)
            NSLog("Pipboy 0b: данные импортированы в зашифрованную базу")
        } catch {
            NSLog("Pipboy 0b: ошибка импорта: \(error)")
        }
    }

    // Уже импортировано, если в зашифрованной базе есть таблица nodes.
    private static func alreadyImported(key: Data) throws -> Bool {
        let db = try Database(key: key)
        return try db.scalarInt(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='nodes'"
        ) > 0
    }

    private static func plaintextSourceURL() -> URL? {
        FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent("Downloads/cladue/app/data.db")
    }

    private static func export(from source: URL, to target: URL, key: Data) throws {
        var src: OpaquePointer?
        guard sqlite3_open_v2(source.path, &src, SQLITE_OPEN_READONLY, nil) == SQLITE_OK else {
            let msg = String(cString: sqlite3_errmsg(src)); sqlite3_close(src)
            throw Failure.sql(msg)
        }
        defer { sqlite3_close(src) }
        let hex = key.map { String(format: "%02x", $0) }.joined()
        try exec(src, "ATTACH DATABASE '\(target.path)' AS enc KEY \"x'\(hex)'\"")
        try exec(src, "SELECT sqlcipher_export('enc')")
        try exec(src, "DETACH DATABASE enc")
    }

    private static func exec(_ db: OpaquePointer?, _ sql: String) throws {
        var err: UnsafeMutablePointer<CChar>?
        if sqlite3_exec(db, sql, nil, nil, &err) != SQLITE_OK {
            let msg = err.map { String(cString: $0) } ?? "unknown"
            sqlite3_free(err)
            throw Failure.sql(msg)
        }
    }
}
