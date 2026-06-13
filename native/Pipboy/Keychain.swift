import Foundation
import Security

// Ключ шифрования базы хранится в keychain приложения.
// Доступ к самому приложению уже под Touch ID (AuthGate на входе), поэтому
// здесь — обычная запись без биометрического access-control: так работает под
// «Sign to Run Locally» без Apple-команды и спец-прав (иначе keychain отдаёт
// errSecMissingEntitlement / -34018). Привязку к Secure Enclave добавим, когда
// заведём команду подписи под iPhone.
enum Keychain {
    enum Failure: Error { case status(OSStatus) }

    private static let service = "com.pipboy.app"
    private static let account = "db-key"

    // Возвращает ключ базы (создаёт 32 случайных байта при первом запуске).
    static func databaseKey() throws -> Data {
        if let existing = try read() { return existing }
        let key = randomBytes(32)
        try store(key)
        return key
    }

    private static func read() throws -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        switch status {
        case errSecSuccess: return item as? Data
        case errSecItemNotFound: return nil
        default: throw Failure.status(status)
        }
    }

    private static func store(_ key: Data) throws {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: key,
        ]
        SecItemDelete(query as CFDictionary)
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else { throw Failure.status(status) }
    }

    private static func randomBytes(_ n: Int) -> Data {
        var d = Data(count: n)
        _ = d.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, n, $0.baseAddress!) }
        return d
    }
}
