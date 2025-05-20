//
//  GardenApp.swift
//  Garden
//
//  Created by Nikita Shilov on 5/21/25.
//

import SwiftUI

@main
struct GardenApp: App {
    let persistenceController = PersistenceController.shared

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(\.managedObjectContext, persistenceController.container.viewContext)
        }
    }
}
