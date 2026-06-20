import SwiftUI

@main
struct ReadAloudApp: App {
    var body: some Scene {
        WindowGroup("Read Aloud") {
            ContentView()
        }
        .windowResizability(.contentSize)
    }
}
