// CLI TrofeoKit : pilote l'écran via la reset-loop (Transport) + Render.
//
//   trofeo-cli run [secondes]   affichage live (horloge + load + uptime), défaut infini
//   trofeo-cli pattern          pousse une mire de test (1 frame)
//   trofeo-cli reset            reset USB seul (diagnostic)

import Foundation
import TrofeoKit

let clockFmt: DateFormatter = { let f = DateFormatter(); f.dateFormat = "HH:mm:ss"; return f }()
let dateFmt: DateFormatter = { let f = DateFormatter(); f.dateFormat = "EEE dd MMM"; return f }()

func uptimeString() -> String {
    let s = Int(ProcessInfo.processInfo.systemUptime)
    let d = s / 86400, h = (s % 86400) / 3600, m = (s % 3600) / 60
    return d > 0 ? "\(d)d \(String(format: "%02d", h))h" : "\(String(format: "%02d", h))h \(String(format: "%02d", m))m"
}

func dashboardFrame() -> [UInt8] {
    var loads = [Double](repeating: 0, count: 3)
    getloadavg(&loads, 3)
    let ncpu = max(1.0, Double(ProcessInfo.processInfo.activeProcessorCount))
    let now = Date()
    let img = Render.dashboard(
        clock: clockFmt.string(from: now),
        date: dateFmt.string(from: now),
        bars: [("LOAD", loads[0] / ncpu)],
        lines: [
            ("LOAD", String(format: "%.2f %.2f %.2f", loads[0], loads[1], loads[2])),
            ("UPTIME", uptimeString()),
        ])
    let jpeg = Render.jpeg(img, quality: 0.9)
    return TrofeoProtocol.buildFrame([UInt8](jpeg), width: Render.width, height: Render.height)
}

func warn(_ s: String) { FileHandle.standardError.write(Data((s + "\n").utf8)) }

let args = CommandLine.arguments
let mode = args.count > 1 ? args[1] : "run"
let device = TrofeoDevice()

switch mode {
case "reset":
    do { try device.resetDevice(); print("reset OK") }
    catch { warn("reset KO: \(error)"); exit(1) }

case "pattern":
    let jpeg = Render.jpeg(Render.testPattern(), quality: 0.9)
    let frame = TrofeoProtocol.buildFrame([UInt8](jpeg), width: Render.width, height: Render.height)
    do { try device.sendFrame(frame); print("mire envoyée") }
    catch { warn("envoi KO: \(error)"); exit(1) }

case "preview":  // rendu vers fichier, sans matériel (vérif du design)
    let dir = args.count > 2 ? args[2] : "/tmp"
    var loads = [Double](repeating: 0, count: 3); getloadavg(&loads, 3)
    let now = Date()
    let dash = Render.dashboard(
        clock: clockFmt.string(from: now), date: dateFmt.string(from: now),
        bars: [("LOAD", loads[0] / max(1.0, Double(ProcessInfo.processInfo.activeProcessorCount)))],
        lines: [("LOAD", String(format: "%.2f %.2f %.2f", loads[0], loads[1], loads[2])), ("UPTIME", uptimeString())])
    try? Render.jpeg(dash, quality: 0.92).write(to: URL(fileURLWithPath: "\(dir)/swift_dashboard.jpg"))
    try? Render.jpeg(Render.testPattern(), quality: 0.92).write(to: URL(fileURLWithPath: "\(dir)/swift_pattern.jpg"))
    print("preview écrit dans \(dir)/swift_dashboard.jpg + swift_pattern.jpg")

default:  // run
    let duration = args.count > 2 ? Double(args[2]) : nil
    let start = Date()
    var ok = 0, ko = 0
    print("Trofeo live (Swift) — Ctrl-C pour arrêter.")
    while true {
        do { try device.sendFrame(dashboardFrame()); ok += 1 }
        catch { ko += 1; warn("frame KO: \(error)") }
        if let duration, Date().timeIntervalSince(start) >= duration { break }
        usleep(330_000)  // ~3 fps
    }
    let el = Date().timeIntervalSince(start)
    print("Fini : \(ok) frames (\(ko) ratées) en \(String(format: "%.1f", el))s ≈ \(String(format: "%.1f", Double(ok) / max(el, 0.001))) fps")
}
