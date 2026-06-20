import WebKit
import Foundation

// Headless smoke test of the WKWebView + Readability.js extraction pipeline.
let urlString = CommandLine.arguments.count > 1
    ? CommandLine.arguments[1]
    : "https://en.wikipedia.org/wiki/Coffee"

let js = try! String(contentsOfFile: "ReadAloud/Resources/Readability.js", encoding: .utf8)

final class Tester: NSObject, WKNavigationDelegate {
    let web = WKWebView()
    func go(_ s: String) {
        web.navigationDelegate = self
        web.customUserAgent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
        web.load(URLRequest(url: URL(string: s)!))
    }
    func webView(_ w: WKWebView, didFinish n: WKNavigation!) {
        let script = js + ";(function(){try{var c=document.cloneNode(true);var a=new Readability(c).parse();if(!a)return JSON.stringify({error:'no-article'});return JSON.stringify({title:a.title,len:a.textContent.length,head:a.textContent.trim().slice(0,300)});}catch(e){return JSON.stringify({error:String(e)});}})();"
        w.evaluateJavaScript(script) { r, e in
            if let e { print("JS ERROR:", e); exit(1) }
            print(r as? String ?? "nil"); exit(0)
        }
    }
    func webView(_ w: WKWebView, didFail n: WKNavigation!, withError e: Error) { print("LOAD FAIL:", e); exit(1) }
    func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) { print("LOAD FAIL:", e); exit(1) }
}

let t = Tester()
t.go(urlString)
RunLoop.main.run(until: Date().addingTimeInterval(30))
print("TIMEOUT"); exit(1)
