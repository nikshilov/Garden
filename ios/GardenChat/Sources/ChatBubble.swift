import SwiftUI
import ExyteChat
import GardenCore

struct ChatBubble: View {
    let message: ExyteChat.Message
    let showCostMeta: Bool
    let metaProvider: (String) -> (cost: Double?, time: TimeInterval?)
    
    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            let isCurrent = message.user.isCurrentUser
            if isCurrent { Spacer(minLength: 40) }
            
            VStack(alignment: isCurrent ? .trailing : .leading, spacing: 4) {
                // Show speaker name for bot messages
                if !isCurrent {
                    HStack {
                        Text(message.user.name)
                            .font(.caption)
                            .fontWeight(.semibold)
                            .foregroundColor(.secondary)
                        Spacer()
                    }
                }
                
                Text(message.text)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 16)
                            .fill(isCurrent ? Color.blue : Color.gray.opacity(0.2))
                    )
                    .foregroundColor(isCurrent ? .white : .primary)
                    .frame(maxWidth: 260, alignment: isCurrent ? .trailing : .leading)
            
                
                if showCostMeta {
                    let meta = metaProvider(message.id)
                    if meta.cost != nil || meta.time != nil {
                        HStack(spacing: 4) {
                            if let cost = meta.cost {
                                Text("$\(String(format: "%.4f", cost))")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                            if let time = meta.time {
                                Text("\(String(format: "%.1f", time))s")
                                    .font(.caption2)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                }
            }
            
            if !isCurrent { Spacer(minLength: 40) }
        }
    }
}
