import Foundation
import Security
import LocalAuthentication

// Общий держатель ключа базы: AuthGate читает ключ под пальцем один раз и кладёт
// сюда; scheme-handler берёт уже расшифрованный ключ (без повторного запроса).
final class KeyHolder {
    static let shared = KeyHolder()
    var key: Data?
}

// Ключ шифрования базы. Основной экземпляр — под биометрией (Secure Enclave ACL,
// .userPresence). Плюс ОТДЕЛЬНАЯ восстановительная копия БЕЗ биометрии (другой
// account), чтобы при сбросе пароля устройства (система удаляет биометрический
// item) доступ к базе не потерялся. Восстановительная копия читается без запроса
// и не пересекается с основным ключом — поэтому лишнего prompt нет.
enum Keychain {
    enum Failure: Error { case status(OSStatus), noKey }
    private enum Read { case found(Data), absent, error(OSStatus) }   // absent ≠ ошибка: только absent даёт право генерировать новый ключ

    private static let service = "com.pipboy.app"
    private static let account = "db-key"                  // основной (биометрия)
    private static let recoveryAccount = "db-key-recovery" // восстановительная копия (без биометрии)

    static func databaseKey(context: LAContext) throws -> Data {
        switch readProtected(context: context) {
        case .found(let k): ensureRecovery(k); return k              // обычный путь: биометрия + гарантируем восстановительную копию
        case .error(let st): throw Failure.status(st)               // транзиентный сбой — НЕ генерируем новый (иначе осиротим базу)
        case .absent: break
        }
        // биометрический ключ отсутствует: первый запуск ИЛИ система удалила его при сбросе пароля
        switch readRecovery() {
        case .found(let k): storeProtected(k, context: context); return k   // восстановили из обычной копии и снова завели под биометрию
        case .error(let st): throw Failure.status(st)
        case .absent: break
        }
        #if os(macOS)
        if case .found(let old) = readLegacyPlain() {               // очень старые установки (file keychain до биометрии)
            storeProtected(old, context: context); _ = storeRecovery(old); return old
        }
        #endif
        // действительно первый запуск
        let key = randomBytes(32)
        let prot = storeProtected(key, context: context)
        let rec = storeRecovery(key)
        if !prot && !rec { throw Failure.noKey }                    // нигде не сохранилось — лучше упасть, чем осиротить базу позже
        return key
    }

    private static func ensureRecovery(_ key: Data) {
        if case .found = readRecovery() { return }
        _ = storeRecovery(key)
    }

    // ----- основной: биометрия (data-protection keychain, .userPresence) -----
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

    // ----- восстановительная копия: БЕЗ биометрии, отдельный account, не бэкапится -----
    private static func readRecovery() -> Read {
        let q: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: recoveryAccount,
            kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne,
            kSecUseDataProtectionKeychain as String: true,
        ]
        var item: CFTypeRef?
        let st = SecItemCopyMatching(q as CFDictionary, &item)
        if st == errSecSuccess, let d = item as? Data { return .found(d) }
        if st == errSecItemNotFound { return .absent }
        return .error(st)
    }

    @discardableResult
    private static func storeRecovery(_ key: Data) -> Bool {
        let q: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service, kSecAttrAccount as String: recoveryAccount,
            kSecValueData as String: key,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly,
            kSecUseDataProtectionKeychain as String: true,
        ]
        SecItemDelete(q as CFDictionary)
        return SecItemAdd(q as CFDictionary, nil) == errSecSuccess
    }

    #if os(macOS)
    // Старый «плоский» ключ из файлового keychain (отдельен от защищённого) — только macOS.
    private static func readLegacyPlain() -> Read {
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
    #endif

    private static func randomBytes(_ n: Int) -> Data {
        var d = Data(count: n)
        _ = d.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, n, $0.baseAddress!) }
        return d
    }
}
