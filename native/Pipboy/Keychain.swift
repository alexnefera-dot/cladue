import Foundation
import Security
import LocalAuthentication

// Ключ шифрования базы хранится в Keychain под защитой Touch ID/пароля.
// Первый запуск — генерируем 32 случайных байта и кладём в Keychain.
// Дальше — читаем только после прохождения LAContext (того же пальца, что на входе).
enum Keychain {
    enum Failure: Error { case status(OSStatus) }

    private static let service = "com.pipboy.app"
    private static let account = "db-key"

    // Возвращает ключ базы (создаёт при первом запуске). context — уже
    // аутентифицированный LAContext из AuthGate, чтобы не спрашивать палец дважды.
    static func databaseKey(context: LAContext) throws -> Data {
        if let existing = try read(context: context) { return existing }
        let key = randomBytes(32)
        try store(key, context: context)
        return key
    }

    private static func read(context: LAContext) throws -> Data? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
            kSecUseAuthenticationContext as String: context,
        ]
        var item: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &item)
        switch status {
        case errSecSuccess: return item as? Data
        case errSecItemNotFound: return nil
        default: throw Failure.status(status)
        }
    }

    private static func store(_ key: Data, context: LAContext) throws {
        guard let access = SecAccessControlCreateWithFlags(
            nil, kSecAttrAccessibleWhenUnlockedThisDeviceOnly, [.userPresence], nil
        ) else { throw Failure.status(errSecParam) }

        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: key,
            kSecAttrAccessControl as String: access,
            kSecUseAuthenticationContext as String: context,
        ]
        SecItemDelete(query as CFDictionary)   // подчистить старую запись, если была
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else { throw Failure.status(status) }
    }

    private static func randomBytes(_ n: Int) -> Data {
        var d = Data(count: n)
        _ = d.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, n, $0.baseAddress!) }
        return d
    }
}
