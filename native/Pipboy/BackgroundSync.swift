#if os(iOS)
import UIKit
import BackgroundTasks

// «Мягкий» фоновый синхрон. iOS изредка выделяет приложению короткое окно
// (Background App Refresh, ~30 c). Синхроним ТОЛЬКО если ключ базы ещё в памяти
// (приложение свёрнуто, но не выгружено системой) — Keychain в фоне не трогаем,
// биометрию не запрашиваем, модель безопасности не меняется. После выгрузки
// приложения из памяти ключа нет → задача просто ничего не делает до открытия.
enum BackgroundSync {
    static let taskId = "com.pipboy.sync.refresh"

    // Регистрируется один раз при запуске (требование iOS — до конца launch).
    static func register() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: taskId, using: nil) { task in
            guard let t = task as? BGAppRefreshTask else { task.setTaskCompleted(success: false); return }
            handle(t)
        }
    }

    // Просим у системы следующий слот. Реальное время решает iOS (раньше — не запустит).
    static func schedule() {
        let req = BGAppRefreshTaskRequest(identifier: taskId)
        req.earliestBeginDate = Date(timeIntervalSinceNow: 15 * 60)
        try? BGTaskScheduler.shared.submit(req)
    }

    private static func handle(_ task: BGAppRefreshTask) {
        schedule()   // сразу заявляем следующий слот, чтобы цепочка не прервалась
        // мягкий фон: только пока ключ в RAM, пара сверена и авто-синхрон включён
        guard KeyHolder.shared.key != nil, SyncTrust.paired, SyncTrust.autoEnabled,
              let sync = SyncService.shared else {
            task.setTaskCompleted(success: false); return
        }
        var finished = false
        let complete: (Bool) -> Void = { ok in
            guard !finished else { return }   // setTaskCompleted можно звать только раз
            finished = true
            task.setTaskCompleted(success: ok)
        }
        task.expirationHandler = { sync.stop(); complete(false) }
        sync.backgroundSyncOnce { ok in complete(ok) }
    }
}

// AppDelegate нужен только чтобы зарегистрировать BG-задачу на старте (SwiftUI App
// сам по себе подходящего хука «до конца launch» не даёт).
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        BackgroundSync.register()
        return true
    }
}
#endif
