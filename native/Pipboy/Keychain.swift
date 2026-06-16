import Foundation
import Security
import LocalAuthentication

// Общий держатель ключа базы: AuthGate читает ключ под пальцем один раз и кладёт
// сюда; scheme-handler берёт уже расшифрованный ключ (без повторного запроса).
final class KeyHolder {
    static let shared = KeyHolder()
    var key: Data?
}

// Ключ шифрования базы. Хранится в Keychain под биометрией (Secure Enclave ACL,
// .userPresence = Touch ID или системный пароль). С миграцией старого «плоского»
// ключа: значение сохраняется, чтобы зашифрованная база всегда открывалась.
// Любой сбой защищённого хранилища → откат к плоскому ключу (не теряем доступ).
enum Keychain {
    enum Failure: Error { case status(OSStatus), noKey }
    private enum Read { case found(Data), absent, error(OSStatus) }   // absent ≠ ошибка: только absent даёт право генерировать новый ключ

    private static let service = "com.pipboy.app"
    private static let account = "db-key"

    static func databaseKey(context: LAContext) throws -> Data {
        switch readProtected(context: context) {
        case .found(let k): ensurePlainFallback(k); return k          // под биометрией + гарантируем копию для восстановления
        case .error(let st): throw Failure.status(st)                 // транзиентный сбой — НЕ генерируем новый (иначе осиротим базу)
        case .absent: break
        }
        switch readPlain() {
        case .found(let old): storeProtected(old, context: context); return old   // система удалила биометрический (сброс пароля) → восстановили из обычной копии
        case .error(let st): throw Failure.status(st)
        case .absent: break
        }
        // оба чтения вернули «нет ключа» наверняка → действительно первый запуск
        let key = randomBytes(32)
        let prot = storeProtected(key, context: context)
        let plain = storePlain(key)                                   // ВСЕГДА держим обычную копию (вариант 1: восстановление при сбросе пароля)
        if !prot && !plain { throw Failure.noKey }                    // нигде не сохранилось — лучше упасть, чем осиротить базу позже
        return key
    }

    // Гарантируем, что обычная (восстановительная) копия ключа существует.
    private static func ensurePlainFallback(_ key: Data) {
        if case .absent = readPlain() { _ = storePlain(key) }
    }

    // ----- защищённое (data-protection keychain, биометрия) -----
    private static func readProtected(context: LAContext) -> Read {
        let q: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: account,
            kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne,
            kSecUseDataProtectionKeychain as String: true,
            kSecUseAuthenticationContext as String: context,
        ]
        var item: CFTypeRef?
        let st = SecItemCopyMatching(q as CFDictionary, &item)
        if st == errSecSuccess, let d = item as? Data { return .found(d) }
        if st == errSecItemNotFound { return .absent }
        return .error(st)
    }

    @discardableResult
    private static func storeProtected(_ key: Data, context: LAContext) -> Bool {
        guard let access = SecAccessControlCreateWithFlags(nil,
            kSecAttrAccessibleWhenUnlockedThisDeviceOnly, [.userPresence], nil) else { return false }
        let q: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: account,
            kSecValueData as String: key, kSecAttrAccessControl as String: access,
            kSecUseDataProtectionKeychain as String: true,
            kSecUseAuthenticationContext as String: context,
        ]
        SecItemDelete(q as CFDictionary)
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }

    // ----- старое плоское (file keychain) -----
    private static func readPlain() -> Read {
        let q: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: account,
            kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        let st = SecItemCopyMatching(q as CFDictionary, &item)
        if st == errSecSuccess, let d = item as? Data { return .found(d) }
        if st == errSecItemNotFound { return .absent }
        return .error(st)
    }
    @discardableResult
    private static func storePlain(_ key: Data) -> Bool {
        let q: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: account,
            kSecValueData as String: key,
        ]
        SecItemDelete(q as CFDictionary)
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }

    private static func randomBytes(_ n: Int) -> Data {
        var d = Data(count: n)
        _ = d.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, n, $0.baseAddress!) }
        return d
    }
}
