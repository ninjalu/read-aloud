import WebKit

/// Loads a URL in an offscreen WKWebView and runs Mozilla's Readability.js to
/// extract clean article text + title. Portable to iOS unchanged.
@MainActor
final class ArticleExtractor: NSObject, WKNavigationDelegate {
    struct Article { let title: String; let text: String }
    enum ExtractError: LocalizedError {
        case badURL, noArticle, js(String), load(String)
        var errorDescription: String? {
            switch self {
            case .badURL:        return "That doesn't look like a valid web address."
            case .noArticle:     return "Couldn't find readable article text on that page."
            case .js(let m):     return "Extraction failed: \(m)"
            case .load(let m):   return "Couldn't load the page: \(m)"
            }
        }
    }

    private var webView: WKWebView!
    private let readabilityJS: String
    private var completion: ((Result<Article, Error>) -> Void)?

    override init() {
        if let url = Bundle.main.url(forResource: "Readability", withExtension: "js"),
           let js = try? String(contentsOf: url, encoding: .utf8) {
            readabilityJS = js
        } else {
            readabilityJS = ""
        }
        super.init()
        let config = WKWebViewConfiguration()
        webView = WKWebView(frame: .zero, configuration: config)
        webView.navigationDelegate = self
        // A realistic UA avoids some sites serving stripped pages to unknown clients.
        webView.customUserAgent =
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    }

    func extract(from urlString: String, completion: @escaping (Result<Article, Error>) -> Void) {
        self.completion = completion
        guard let url = Self.normalizedURL(urlString) else { finish(.failure(ExtractError.badURL)); return }
        webView.load(URLRequest(url: url))
    }

    static func normalizedURL(_ raw: String) -> URL? {
        var s = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !s.isEmpty else { return nil }
        if !s.lowercased().hasPrefix("http://") && !s.lowercased().hasPrefix("https://") {
            s = "https://" + s
        }
        guard let url = URL(string: s), url.host != nil else { return nil }
        return url
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let script = readabilityJS + """
        ;(function () {
          try {
            var clone = document.cloneNode(true);
            var article = new Readability(clone).parse();
            if (!article || !article.textContent || !article.textContent.trim()) {
              return JSON.stringify({ error: "no-article" });
            }
            return JSON.stringify({
              title: (article.title || document.title || "").trim(),
              text: article.textContent.replace(/\\n{3,}/g, "\\n\\n").trim()
            });
          } catch (e) { return JSON.stringify({ error: String(e && e.message || e) }); }
        })();
        """
        webView.evaluateJavaScript(script) { [weak self] result, error in
            guard let self else { return }
            if let error { self.finish(.failure(ExtractError.js(error.localizedDescription))); return }
            guard let json = result as? String, let data = json.data(using: .utf8),
                  let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                self.finish(.failure(ExtractError.noArticle)); return
            }
            if let err = obj["error"] as? String {
                self.finish(.failure(err == "no-article" ? ExtractError.noArticle : ExtractError.js(err)))
                return
            }
            let title = obj["title"] as? String ?? ""
            let text  = obj["text"] as? String ?? ""
            self.finish(.success(Article(title: title, text: text)))
        }
    }

    func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
        finish(.failure(ExtractError.load(error.localizedDescription)))
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        finish(.failure(ExtractError.load(error.localizedDescription)))
    }

    private func finish(_ result: Result<Article, Error>) {
        let c = completion
        completion = nil
        c?(result)
    }
}
