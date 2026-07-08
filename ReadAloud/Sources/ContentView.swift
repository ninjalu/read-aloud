import SwiftUI

struct ContentView: View {
    @StateObject private var reader = KokoroReader()
    @StateObject private var vm = ExtractorVM()

    @State private var urlText = ""
    @State private var title = ""
    @State private var sourceURL = ""   // the URL actually loaded, recorded on the podcast episode

    var body: some View {
        VStack(spacing: 0) {
            inputBar
            Divider()
            engineBanner
            if let err = vm.errorMessage {
                banner(err, systemImage: "exclamationmark.triangle.fill", color: .orange)
            }
            articleView
            Divider()
            transportBar
        }
        .frame(minWidth: 580, minHeight: 620)
        .onAppear { reader.startEngine() }
    }

    // MARK: URL input

    private var inputBar: some View {
        HStack(spacing: 8) {
            Image(systemName: "link").foregroundStyle(.secondary)
            TextField("Paste an article URL and press Return…", text: $urlText)
                .textFieldStyle(.plain)
                .onSubmit(read)
            if vm.isLoading {
                ProgressView().controlSize(.small)
            } else {
                Button("Read", action: read)
                    .keyboardShortcut(.return, modifiers: [])
                    .disabled(urlText.trimmingCharacters(in: .whitespaces).isEmpty)
            }
        }
        .padding(12)
    }

    @ViewBuilder private var engineBanner: some View {
        switch reader.engine {
        case .starting:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Starting the Kokoro voice engine… (first launch loads the model, ~10–20s)")
                    .font(.callout)
                Spacer()
            }
            .padding(.horizontal, 12).padding(.vertical, 8)
            .background(Color.blue.opacity(0.10))
        case .failed(let msg):
            banner(msg, systemImage: "xmark.octagon.fill", color: .red)
        case .ready:
            EmptyView()
        }
    }

    // MARK: Article text with current-sentence highlight

    private var articleView: some View {
        ScrollViewReader { proxy in
            ScrollView {
                VStack(alignment: .leading, spacing: 10) {
                    if !title.isEmpty {
                        Text(title).font(.title2.bold()).padding(.bottom, 4)
                    }
                    if reader.sentences.isEmpty {
                        Text("Your article will appear here. Tap any sentence to jump to it.")
                            .foregroundStyle(.secondary).padding(.top, 40)
                    }
                    ForEach(Array(reader.sentences.enumerated()), id: \.offset) { idx, sentence in
                        Text(sentence)
                            .id(idx)
                            .padding(.horizontal, 6).padding(.vertical, 3)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(idx == reader.currentIndex && reader.state != .idle
                                        ? Color.accentColor.opacity(0.18) : .clear,
                                        in: RoundedRectangle(cornerRadius: 5))
                            .contentShape(Rectangle())
                            .onTapGesture { reader.jump(to: idx) }
                    }
                }
                .font(.system(size: 17))
                .lineSpacing(4)
                .padding(16)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .onChange(of: reader.currentIndex) { _, new in
                withAnimation { proxy.scrollTo(new, anchor: .center) }
            }
        }
    }

    // MARK: Transport + settings

    private var transportBar: some View {
        VStack(spacing: 10) {
            HStack(spacing: 28) {
                Button(action: reader.skipBackward) { Image(systemName: "backward.fill") }
                    .disabled(!reader.isLoaded)
                Button(action: reader.togglePlayPause) {
                    Image(systemName: reader.state == .playing ? "pause.circle.fill" : "play.circle.fill")
                        .font(.system(size: 44))
                }
                .disabled(!reader.isLoaded || !reader.isReady)
                Button(action: reader.skipForward) { Image(systemName: "forward.fill") }
                    .disabled(!reader.isLoaded)
            }
            .buttonStyle(.plain)
            .font(.system(size: 22))

            HStack(spacing: 16) {
                Image(systemName: "tortoise.fill").foregroundStyle(.secondary)
                Slider(value: $reader.rateFraction, in: 0...1)
                Image(systemName: "hare.fill").foregroundStyle(.secondary)

                Picker("", selection: $reader.voice) {
                    ForEach(KokoroReader.voices) { v in
                        Text(v.label).tag(v.id)
                    }
                }
                .frame(width: 230)
            }

            HStack(spacing: 10) {
                Button {
                    reader.export(title: title, sourceURL: sourceURL)
                } label: {
                    Label("Export MP3", systemImage: "square.and.arrow.down")
                }
                .disabled(!reader.isLoaded || !reader.isReady || reader.exporting)

                if reader.exporting {
                    ProgressView().controlSize(.small)
                    Text("Exporting & adding to podcast… long articles take a minute")
                        .font(.caption).foregroundStyle(.secondary)
                } else if let result = reader.exportResult {
                    Image(systemName: reader.exportOK ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                        .foregroundStyle(reader.exportOK ? .green : .orange)
                    Text(result).font(.caption)
                        .foregroundStyle(reader.exportOK ? Color.secondary : .orange)
                        .lineLimit(2)
                }
                Spacer()
            }
        }
        .padding(14)
        .alert("Couldn’t add this episode to the podcast", isPresented: $reader.showPublishError) {
            Button("OK", role: .cancel) {}
        } message: {
            Text(reader.exportResult ?? "The publish step failed. Run ./podcast-sync to retry.")
        }
    }

    private func banner(_ text: String, systemImage: String, color: Color) -> some View {
        HStack(spacing: 8) {
            Image(systemName: systemImage).foregroundStyle(color)
            Text(text).font(.callout)
            Spacer()
        }
        .padding(.horizontal, 12).padding(.vertical, 8)
        .background(color.opacity(0.12))
    }

    private func read() {
        let url = urlText.trimmingCharacters(in: .whitespaces)
        guard !url.isEmpty else { return }
        reader.stop()
        title = ""
        sourceURL = url                 // remember what we loaded, for the podcast episode record
        vm.extract(url) { article in
            title = article.title
            reader.load(text: article.text)
            reader.play()
        }
    }
}

/// Small ObservableObject so the extractor's async result drives SwiftUI state.
@MainActor
final class ExtractorVM: ObservableObject {
    @Published var isLoading = false
    @Published var errorMessage: String?
    private let extractor = ArticleExtractor()

    func extract(_ url: String, onSuccess: @escaping (ArticleExtractor.Article) -> Void) {
        isLoading = true
        errorMessage = nil
        extractor.extract(from: url) { [weak self] result in
            guard let self else { return }
            self.isLoading = false
            switch result {
            case .success(let article): onSuccess(article)
            case .failure(let error):   self.errorMessage = error.localizedDescription
            }
        }
    }
}
