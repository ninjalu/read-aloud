import AVFoundation
import SwiftUI
import AppKit

struct KokoroVoice: Identifiable, Hashable { let id: String; let label: String }

/// Drives playback by requesting one sentence at a time from the local Kokoro
/// TTS server, playing each with AVAudioPlayer and prefetching the next so
/// there are no gaps. Keeps the same play/pause/skip/jump surface the UI uses.
@MainActor
final class KokoroReader: NSObject, ObservableObject, AVAudioPlayerDelegate {
    enum PlayState { case idle, playing, paused }
    enum Engine: Equatable { case starting, ready, failed(String) }

    @Published var sentences: [String] = []
    @Published var currentIndex = 0
    @Published var state: PlayState = .idle
    @Published var engine: Engine = .starting
    @Published var exporting = false
    @Published var exportResult: String?
    @Published var exportOK = true
    @Published var showPublishError = false
    private(set) var fullText = ""

    @Published var rateFraction: Double = 0.5 { didSet { player?.rate = mappedRate() } }
    @Published var voice: String = "bm_lewis" { didSet { onVoiceChanged() } }

    static let voices: [KokoroVoice] = [
        .init(id: "bm_lewis",    label: "Lewis · British male"),
        .init(id: "bm_george",   label: "George · British male"),
        .init(id: "bf_emma",     label: "Emma · British female"),
        .init(id: "bf_isabella", label: "Isabella · British female"),
        .init(id: "am_michael",  label: "Michael · American male"),
        .init(id: "am_adam",     label: "Adam · American male"),
        .init(id: "af_heart",    label: "Heart · American female"),
        .init(id: "af_bella",    label: "Bella · American female"),
    ]

    private let port = 8770
    private var base: URL { URL(string: "http://127.0.0.1:\(port)")! }
    private var player: AVAudioPlayer?
    private var cache: [Int: Data] = [:]
    private var prefetch: [Int: Task<Void, Never>] = [:]
    private var serverProc: Process?
    private var autoAdvance = true
    private var pendingPlay = false
    /// Bumped on load/stop/voice-change to invalidate in-flight fetches.
    private var generation = 0

    var isLoaded: Bool { !sentences.isEmpty }
    var isReady: Bool { engine == .ready }

    // MARK: - Content

    func load(text: String) {
        stop()
        generation &+= 1
        cache.removeAll()
        fullText = text
        exportResult = nil
        sentences = Self.splitSentences(text)
        currentIndex = 0
    }

    // MARK: - Transport

    func togglePlayPause() {
        switch state {
        case .playing: pause()
        case .paused:  resume()
        case .idle:    play()
        }
    }

    func play() {
        guard isLoaded else { return }
        guard isReady else { pendingPlay = true; return }   // start once the engine is up
        if state == .paused { resume(); return }
        if state == .playing { return }
        let gen = generation
        Task { await playFrom(currentIndex, gen: gen) }
    }

    func pause()  { if state == .playing { player?.pause(); state = .paused } }
    func resume() { if state == .paused  { player?.play();  state = .playing } }

    func stop() {
        autoAdvance = false
        player?.stop()
        player = nil
        state = .idle
    }

    func skipForward()  { jump(to: currentIndex + 1) }
    func skipBackward() { jump(to: currentIndex - 1) }

    func jump(to index: Int) {
        guard isLoaded else { return }
        let i = max(0, min(index, sentences.count - 1))
        let wasActive = (state != .idle)
        autoAdvance = false
        player?.stop()
        currentIndex = i
        if wasActive && isReady {
            let gen = generation
            Task { await playFrom(i, gen: gen) }
        } else {
            state = .idle
        }
    }

    // MARK: - Playback engine

    private func playFrom(_ i: Int, gen: Int) async {
        guard i < sentences.count else { state = .idle; currentIndex = 0; return }
        currentIndex = i
        autoAdvance = true
        guard let data = await fetch(i, gen: gen), gen == generation else { return }
        startPlayer(with: data)
        state = .playing
        schedulePrefetch(i + 1, gen: gen)
    }

    private func startPlayer(with data: Data) {
        player?.stop()
        player = try? AVAudioPlayer(data: data)
        player?.delegate = self
        player?.enableRate = true
        player?.rate = mappedRate()
        player?.prepareToPlay()
        player?.play()
    }

    /// 0…1 slider → 0.5×…1.5× playback speed (time-stretch, no re-synthesis).
    private func mappedRate() -> Float { Float(0.5 + rateFraction) }

    private func schedulePrefetch(_ i: Int, gen: Int) {
        guard i < sentences.count, cache[i] == nil, prefetch[i] == nil else { return }
        prefetch[i] = Task { [weak self] in
            _ = await self?.fetch(i, gen: gen)
            await MainActor.run { self?.prefetch[i] = nil }
        }
    }

    private func fetch(_ i: Int, gen: Int) async -> Data? {
        if let cached = cache[i] { return cached }
        guard i < sentences.count, gen == generation else { return nil }
        var comp = URLComponents(url: base.appendingPathComponent("speak"), resolvingAgainstBaseURL: false)!
        comp.queryItems = [.init(name: "voice", value: voice), .init(name: "speed", value: "1.0")]
        var req = URLRequest(url: comp.url!)
        req.httpMethod = "POST"
        req.httpBody = sentences[i].data(using: .utf8)
        req.timeoutInterval = 60
        do {
            let (data, resp) = try await URLSession.shared.data(for: req)
            guard gen == generation, (resp as? HTTPURLResponse)?.statusCode == 200, !data.isEmpty else { return nil }
            cache[i] = data
            return data
        } catch { return nil }
    }

    private func onVoiceChanged() {
        generation &+= 1
        cache.removeAll()
        prefetch.values.forEach { $0.cancel() }
        prefetch.removeAll()
        if state != .idle {
            let i = currentIndex, gen = generation
            player?.stop()
            Task { await playFrom(i, gen: gen) }
        }
    }

    // MARK: - AVAudioPlayerDelegate

    nonisolated func audioPlayerDidFinishPlaying(_ p: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in
            guard self.autoAdvance else { return }
            let next = self.currentIndex + 1
            let gen = self.generation
            if next < self.sentences.count { await self.playFrom(next, gen: gen) }
            else { self.state = .idle; self.currentIndex = 0 }
        }
    }

    // MARK: - Server lifecycle

    func startEngine() {
        Task { await ensureServer() }
    }

    private func ensureServer() async {
        if await healthy() { engineReady(); return }

        // Project root is two levels up from build/ReadAloud.app
        let projectDir = Bundle.main.bundleURL
            .deletingLastPathComponent()   // build/
            .deletingLastPathComponent()   // project root
        let proc = Process()
        proc.executableURL = projectDir.appendingPathComponent(".venv/bin/python")
        proc.arguments = [projectDir.appendingPathComponent("tts_server.py").path, "\(port)"]
        proc.currentDirectoryURL = projectDir
        proc.standardOutput = FileHandle.nullDevice
        proc.standardError = FileHandle.nullDevice
        do { try proc.run(); serverProc = proc }
        catch { engine = .failed("Couldn't launch the voice server: \(error.localizedDescription)"); return }

        for _ in 0..<120 {                       // up to ~60s for first model load
            try? await Task.sleep(nanoseconds: 500_000_000)
            if await healthy() { engineReady(); return }
        }
        engine = .failed("Voice server didn't become ready in time.")
    }

    private func engineReady() {
        engine = .ready
        if pendingPlay { pendingPlay = false; play() }
    }

    private func healthy() async -> Bool {
        var req = URLRequest(url: base.appendingPathComponent("health"))
        req.timeoutInterval = 2
        guard let (d, r) = try? await URLSession.shared.data(for: req),
              (r as? HTTPURLResponse)?.statusCode == 200 else { return false }
        return String(data: d, encoding: .utf8) == "ok"
    }

    // MARK: - MP3 export

    func export(title: String, sourceURL: String = "") {
        guard isReady, !fullText.isEmpty, !exporting else { return }
        exporting = true
        exportResult = nil
        let voice = self.voice
        let text = self.fullText
        let safeTitle = title.isEmpty ? "Article" : title
        Task {
            let (msg, ok) = await performExport(title: safeTitle, text: text, voice: voice, sourceURL: sourceURL)
            self.exporting = false
            self.exportResult = msg
            self.exportOK = ok
            if !ok { self.showPublishError = true }   // pop a real alert, don't hide it in a caption
        }
    }

    /// Returns (user-facing message, ok). `ok == false` means the MP3 may exist
    /// but it did NOT make it into the podcast feed — surfaced as a modal alert.
    private func performExport(title: String, text: String, voice: String, sourceURL: String) async -> (String, Bool) {
        var comp = URLComponents(url: base.appendingPathComponent("export"), resolvingAgainstBaseURL: false)!
        comp.queryItems = [.init(name: "voice", value: voice), .init(name: "title", value: title)]
        var req = URLRequest(url: comp.url!)
        req.httpMethod = "POST"
        req.httpBody = text.data(using: .utf8)
        req.timeoutInterval = 1800   // whole-article synthesis can take a while
        do {
            let (data, resp) = try await URLSession.shared.data(for: req)
            guard (resp as? HTTPURLResponse)?.statusCode == 200, !data.isEmpty else {
                return ("Export failed — the TTS server returned an error.", false)
            }
            let dir = Self.exportDirectory()
            let fileURL = dir.appendingPathComponent(Self.safeFilename(title) + ".mp3")
            try data.write(to: fileURL)
            NSWorkspace.shared.activateFileViewerSelecting([fileURL])
            let where_ = dir.path.contains("Mobile Documents") ? "iCloud Drive › ReadAloud" : dir.path
            let saved = "Saved “\(fileURL.lastPathComponent)” to \(where_)"
            // Register + publish this file to the private podcast feed, source link intact.
            let published = await publishToPodcast(fileURL: fileURL, title: title,
                                                   sourceURL: sourceURL, voice: voice)
            if published {
                return (saved + " · added to podcast ✓", true)
            }
            // Saved locally but not published. The folder-watcher LaunchAgent
            // (com.readaloud.podcast-sync) should retry within ~20s; the fix
            // command is a manual backstop.
            return (saved + ", but it isn’t in the podcast feed yet. "
                    + "The auto-sync watcher will retry shortly — or run ./podcast-sync to force it.",
                    false)
        } catch {
            return ("Export failed: \(error.localizedDescription)", false)
        }
    }

    /// Run `podcast.py add` in the project venv to register the just-exported MP3
    /// (with its source URL) and rebuild + upload the feed. Returns true on success.
    private func publishToPodcast(fileURL: URL, title: String,
                                  sourceURL: String, voice: String) async -> Bool {
        let projectDir = Bundle.main.bundleURL
            .deletingLastPathComponent()   // build/
            .deletingLastPathComponent()   // project root
        let py = projectDir.appendingPathComponent(".venv/bin/python")
        let script = projectDir.appendingPathComponent("podcast.py")
        let fm = FileManager.default
        guard fm.fileExists(atPath: py.path), fm.fileExists(atPath: script.path) else { return false }

        var args = [script.path, "add",
                    "--library", fileURL.deletingLastPathComponent().path,
                    "--file", fileURL.path, "--voice", voice]
        if !title.isEmpty { args += ["--title", title] }
        if !sourceURL.isEmpty { args += ["--url", sourceURL] }

        let proc = Process()
        proc.executableURL = py
        proc.currentDirectoryURL = projectDir
        proc.arguments = args
        proc.standardOutput = FileHandle.nullDevice
        proc.standardError = FileHandle.nullDevice
        return await withCheckedContinuation { cont in
            proc.terminationHandler = { cont.resume(returning: $0.terminationStatus == 0) }
            do { try proc.run() } catch { cont.resume(returning: false) }
        }
    }

    /// Prefer an iCloud Drive folder so exports auto-sync to the iPhone Files app.
    static func exportDirectory() -> URL {
        let fm = FileManager.default
        let home = URL(fileURLWithPath: NSHomeDirectory())
        let icloud = home.appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs")
        let dir = fm.fileExists(atPath: icloud.path)
            ? icloud.appendingPathComponent("ReadAloud")
            : home.appendingPathComponent("ReadAloud")
        try? fm.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir
    }

    static func safeFilename(_ s: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(.whitespaces).union(CharacterSet(charactersIn: "-_"))
        let cleaned = String(s.unicodeScalars.filter { allowed.contains($0) }).trimmingCharacters(in: .whitespaces)
        let name = String(cleaned.prefix(80)).replacingOccurrences(of: " ", with: "_")
        return name.isEmpty ? "article" : name
    }

    // MARK: - Sentence splitting (locale-aware)

    static func splitSentences(_ text: String) -> [String] {
        let cleaned = text.replacingOccurrences(of: "\r", with: "\n")
        var result: [String] = []
        // Split on line breaks first so each heading and bullet item becomes its
        // own chunk (and thus gets a clean pause), then sentence-split within a
        // line for long paragraphs. Splitting only by sentences would let a
        // bullet with no terminal punctuation merge into its neighbour.
        for line in cleaned.components(separatedBy: "\n") {
            let trimmedLine = line.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmedLine.isEmpty { continue }
            trimmedLine.enumerateSubstrings(in: trimmedLine.startIndex..<trimmedLine.endIndex,
                                            options: .bySentences) { sub, _, _, _ in
                let s = sub?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                if !s.isEmpty { result.append(s) }
            }
        }
        if result.isEmpty {
            let t = cleaned.trimmingCharacters(in: .whitespacesAndNewlines)
            if !t.isEmpty { result = [t] }
        }
        return result
    }
}
