import Foundation
import CryptoKit
import CommonCrypto

// Пароль на отдельную заметку Инфо. Формат совместим с Node (notes.js):
// scrypt(пароль, соль, 32) → AES-256-GCM, JSON {s,i,t,d} в base64.
// ВНИМАНИЕ: scrypt реализован вручную (в Swift его нет) — проверить на реальной
// запароленной странице, что старые (зашифрованные Node) открываются.
enum PageCrypto {
    enum Err: Error { case badPassword, format }

    static func encrypt(password: String, text: String) throws -> String {
        let salt = randomData(16)
        let key = scrypt(password: Data(password.utf8), salt: salt, n: 16384, r: 8, p: 1, dkLen: 32)
        let iv = randomData(12)
        let sealed = try AES.GCM.seal(Data(text.utf8), using: SymmetricKey(data: key), nonce: try AES.GCM.Nonce(data: iv))
        let obj = ["s": salt.base64EncodedString(), "i": iv.base64EncodedString(),
                   "t": sealed.tag.base64EncodedString(), "d": sealed.ciphertext.base64EncodedString()]
        return String(data: try JSONSerialization.data(withJSONObject: obj), encoding: .utf8) ?? "{}"
    }

    static func decrypt(password: String, encStr: String) throws -> String {
        guard let obj = (try? JSONSerialization.jsonObject(with: Data(encStr.utf8))) as? [String: String],
              let s = obj["s"].flatMap({ Data(base64Encoded: $0) }),
              let i = obj["i"].flatMap({ Data(base64Encoded: $0) }),
              let t = obj["t"].flatMap({ Data(base64Encoded: $0) }),
              let d = obj["d"].flatMap({ Data(base64Encoded: $0) }) else { throw Err.format }
        let key = scrypt(password: Data(password.utf8), salt: s, n: 16384, r: 8, p: 1, dkLen: 32)
        do {
            let box = try AES.GCM.SealedBox(nonce: try AES.GCM.Nonce(data: i), ciphertext: d, tag: t)
            return String(data: try AES.GCM.open(box, using: SymmetricKey(data: key)), encoding: .utf8) ?? ""
        } catch { throw Err.badPassword }
    }

    private static func randomData(_ n: Int) -> Data {
        var d = Data(count: n); _ = d.withUnsafeMutableBytes { SecRandomCopyBytes(kSecRandomDefault, n, $0.baseAddress!) }
        return d
    }

    // ===== scrypt (RFC 7914) =====
    static func scrypt(password: Data, salt: Data, n: Int, r: Int, p: Int, dkLen: Int) -> Data {
        let mfLen = 128 * r
        var b = [UInt8](pbkdf2(password: password, salt: salt, keyLen: p * mfLen))
        for i in 0..<p {
            var words = bytesToWords(Array(b[i * mfLen ..< (i + 1) * mfLen]))
            romix(&words, n: n, r: r)
            let bytes = wordsToBytes(words)
            for j in 0..<mfLen { b[i * mfLen + j] = bytes[j] }
        }
        return pbkdf2(password: password, salt: Data(b), keyLen: dkLen)
    }

    private static func pbkdf2(password: Data, salt: Data, keyLen: Int) -> Data {
        var dk = Data(count: keyLen)
        let status = dk.withUnsafeMutableBytes { dkPtr in
            password.withUnsafeBytes { pwPtr in
                salt.withUnsafeBytes { saltPtr in
                    CCKeyDerivationPBKDF(CCPBKDFAlgorithm(kCCPBKDF2),
                        pwPtr.bindMemory(to: Int8.self).baseAddress, password.count,
                        saltPtr.bindMemory(to: UInt8.self).baseAddress, salt.count,
                        CCPseudoRandomAlgorithm(kCCPRFHmacAlgSHA256), 1,
                        dkPtr.bindMemory(to: UInt8.self).baseAddress, keyLen)
                }
            }
        }
        _ = status
        return dk
    }

    private static func romix(_ b: inout [UInt32], n: Int, r: Int) {
        let words = 32 * r
        var x = b
        var v: [[UInt32]] = []; v.reserveCapacity(n)
        for _ in 0..<n { v.append(x); x = blockMix(x, r: r) }
        for _ in 0..<n {
            let j = Int(x[(2 * r - 1) * 16]) % n   // integerify: первое слово последнего блока (LE)
            var t = x
            for k in 0..<words { t[k] ^= v[j][k] }
            x = blockMix(t, r: r)
        }
        b = x
    }

    private static func blockMix(_ b: [UInt32], r: Int) -> [UInt32] {
        var x = Array(b[(2 * r - 1) * 16 ..< (2 * r) * 16])
        var out = [UInt32](repeating: 0, count: b.count)
        for i in 0..<(2 * r) {
            for j in 0..<16 { x[j] ^= b[i * 16 + j] }
            salsa20_8(&x)
            let dest = (i % 2 == 0) ? (i / 2) : (r + (i - 1) / 2)
            for j in 0..<16 { out[dest * 16 + j] = x[j] }
        }
        return out
    }

    private static func salsa20_8(_ b: inout [UInt32]) {
        func R(_ a: UInt32, _ s: UInt32) -> UInt32 { (a << s) | (a >> (32 - s)) }
        var x = b
        for _ in 0..<4 {
            x[ 4] ^= R(x[ 0] &+ x[12],  7); x[ 8] ^= R(x[ 4] &+ x[ 0],  9)
            x[12] ^= R(x[ 8] &+ x[ 4], 13); x[ 0] ^= R(x[12] &+ x[ 8], 18)
            x[ 9] ^= R(x[ 5] &+ x[ 1],  7); x[13] ^= R(x[ 9] &+ x[ 5],  9)
            x[ 1] ^= R(x[13] &+ x[ 9], 13); x[ 5] ^= R(x[ 1] &+ x[13], 18)
            x[14] ^= R(x[10] &+ x[ 6],  7); x[ 2] ^= R(x[14] &+ x[10],  9)
            x[ 6] ^= R(x[ 2] &+ x[14], 13); x[10] ^= R(x[ 6] &+ x[ 2], 18)
            x[ 3] ^= R(x[15] &+ x[11],  7); x[ 7] ^= R(x[ 3] &+ x[15],  9)
            x[11] ^= R(x[ 7] &+ x[ 3], 13); x[15] ^= R(x[11] &+ x[ 7], 18)
            x[ 1] ^= R(x[ 0] &+ x[ 3],  7); x[ 2] ^= R(x[ 1] &+ x[ 0],  9)
            x[ 3] ^= R(x[ 2] &+ x[ 1], 13); x[ 0] ^= R(x[ 3] &+ x[ 2], 18)
            x[ 6] ^= R(x[ 5] &+ x[ 4],  7); x[ 7] ^= R(x[ 6] &+ x[ 5],  9)
            x[ 4] ^= R(x[ 7] &+ x[ 6], 13); x[ 5] ^= R(x[ 4] &+ x[ 7], 18)
            x[11] ^= R(x[10] &+ x[ 9],  7); x[ 8] ^= R(x[11] &+ x[10],  9)
            x[ 9] ^= R(x[ 8] &+ x[11], 13); x[10] ^= R(x[ 9] &+ x[ 8], 18)
            x[12] ^= R(x[15] &+ x[14],  7); x[13] ^= R(x[12] &+ x[15],  9)
            x[14] ^= R(x[13] &+ x[12], 13); x[15] ^= R(x[14] &+ x[13], 18)
        }
        for i in 0..<16 { b[i] = b[i] &+ x[i] }
    }

    private static func bytesToWords(_ bytes: [UInt8]) -> [UInt32] {
        var w = [UInt32](repeating: 0, count: bytes.count / 4)
        for i in 0..<w.count {
            w[i] = UInt32(bytes[4 * i]) | (UInt32(bytes[4 * i + 1]) << 8) | (UInt32(bytes[4 * i + 2]) << 16) | (UInt32(bytes[4 * i + 3]) << 24)
        }
        return w
    }
    private static func wordsToBytes(_ words: [UInt32]) -> [UInt8] {
        var b = [UInt8](repeating: 0, count: words.count * 4)
        for i in 0..<words.count {
            let v = words[i]
            b[4 * i] = UInt8(v & 0xff); b[4 * i + 1] = UInt8((v >> 8) & 0xff)
            b[4 * i + 2] = UInt8((v >> 16) & 0xff); b[4 * i + 3] = UInt8((v >> 24) & 0xff)
        }
        return b
    }
}
