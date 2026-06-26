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
        // Pasted links often carry invisible passengers (zero-width spaces, BOM,
        // bidi marks) or wrapping punctuation that make URL(string:) return nil.
        // Strip them before parsing so a perfectly good URL isn't rejected.
        let invisibles = CharacterSet(charactersIn:
            "\u{200B}\u{200C}\u{200D}\u{200E}\u{200F}\u{202A}\u{202B}\u{202C}\u{202D}\u{202E}\u{2060}\u{FEFF}")
            .union(.controlCharacters)
        s = String(s.unicodeScalars.filter { !invisibles.contains($0) })
        s = s.trimmingCharacters(in: CharacterSet(charactersIn: "<>\"'`“”‘’ "))
        guard !s.isEmpty else { return nil }
        if !s.lowercased().hasPrefix("http://") && !s.lowercased().hasPrefix("https://") {
            s = "https://" + s
        }
        if let url = URL(string: s), url.host != nil { return url }
        // Last resort: percent-encode any remaining illegal characters and retry.
        if #available(macOS 14.0, *),
           let url = URL(string: s, encodingInvalidCharacters: true), url.host != nil {
            return url
        }
        return nil
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        let script = readabilityJS + """
        ;(function () {
          try {
            var clone = document.cloneNode(true);
            var article = new Readability(clone).parse();
            if (!article || !article.content) {
              return JSON.stringify({ error: "no-article" });
            }
            // Walk the cleaned article HTML rather than using textContent, so
            // structure survives for the TTS: every list item and heading ends
            // with a full stop (giving a falling intonation + pause), and blocks
            // are separated by blank lines. textContent alone runs bullets and
            // sections together because the markup carries the breaks, not text.
            var host = document.createElement("div");
            host.innerHTML = article.content;
            var ENDS = /[.!?:;)\\]"'’”…]$/;
            function ensureStop(s) {
              s = s.replace(/\\s+/g, " ").trim();
              if (!s) return "";
              return ENDS.test(s) ? s : s + ".";
            }
            function walk(node) {
              var out = "";
              node.childNodes.forEach(function (child) {
                if (child.nodeType === 3) {
                  out += child.textContent.replace(/\\s+/g, " ");
                } else if (child.nodeType === 1) {
                  var tag = child.tagName.toLowerCase();
                  if (tag === "br") { out += "\\n"; return; }
                  if (tag === "script" || tag === "style" || tag === "noscript") return;
                  var inner = walk(child);
                  if (/^h[1-6]$/.test(tag)) {
                    out += "\\n\\n" + ensureStop(inner) + "\\n\\n";
                  } else if (tag === "ol") {
                    // Ordered-list numbers come from CSS, not text, so they'd be
                    // silent. Emit them explicitly, honouring any start offset.
                    var n = parseInt(child.getAttribute("start"), 10);
                    if (isNaN(n)) n = 1;
                    var items = "";
                    child.childNodes.forEach(function (li) {
                      if (li.nodeType === 1 && li.tagName.toLowerCase() === "li") {
                        var v = parseInt(li.getAttribute("value"), 10);
                        if (!isNaN(v)) n = v;
                        items += ensureStop(n + ". " + walk(li)) + "\\n";
                        n += 1;
                      } else {
                        items += walk(li);
                      }
                    });
                    out += "\\n" + items + "\\n";
                  } else if (tag === "li") {
                    out += ensureStop(inner) + "\\n";
                  } else if (tag === "p" || tag === "div" || tag === "ul" ||
                             tag === "section" || tag === "article" ||
                             tag === "blockquote" || tag === "figcaption" || tag === "tr") {
                    out += "\\n" + inner + "\\n";
                  } else {
                    out += inner;
                  }
                }
              });
              return out;
            }
            var text = walk(host)
              .replace(/[ \\t]+\\n/g, "\\n")
              .replace(/[ \\t]{2,}/g, " ")
              .replace(/\\n{3,}/g, "\\n\\n")
              .trim();
            if (!text) { return JSON.stringify({ error: "no-article" }); }
            return JSON.stringify({
              title: (article.title || document.title || "").trim(),
              text: text
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
