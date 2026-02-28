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
            
            if !isCurrent {
                Circle()
                    .fill(LinearGradient(colors: [.blue.opacity(0.3), .purple.opacity(0.3)], startPoint: .topLeading, endPoint: .bottomTrailing))
                    .frame(width: 32, height: 32)
                    .overlay(
                        Text(message.user.name.prefix(1).uppercased())
                            .font(.system(size: 14, weight: .bold))
                            .foregroundColor(.white)
                    )
                    .shadow(color: .black.opacity(0.1), radius: 2, x: 0, y: 1)
            }
            
            VStack(alignment: isCurrent ? .trailing : .leading, spacing: 4) {
                if !isCurrent {
                    Text(message.user.name)
                        .font(.system(size: 12, weight: .semibold, design: .rounded))
                        .foregroundColor(.secondary)
                        .padding(.leading, 4)
                }
                
                Text(message.text)
                    .font(.system(size: 16, weight: .regular, design: .rounded))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(
                        ZStack {
                            if isCurrent {
                                LinearGradient(colors: [Color.blue, Color.blue.opacity(0.8)], startPoint: .topLeading, endPoint: .bottomTrailing)
                            } else {
                                Color(.secondarySystemBackground)
                            }
                        }
                    )
                    .clipShape(BubbleShape(isCurrent: isCurrent))
                    .foregroundColor(isCurrent ? .white : .primary)
                    .shadow(color: isCurrent ? Color.blue.opacity(0.3) : Color.black.opacity(0.05), radius: 5, x: 0, y: 3)
                    .frame(maxWidth: UIScreen.main.bounds.width * 0.75, alignment: isCurrent ? .trailing : .leading)
            
                if showCostMeta {
                    let meta = metaProvider(message.id)
                    if meta.cost != nil || meta.time != nil {
                        HStack(spacing: 8) {
                            if let cost = meta.cost {
                                Label("$\(String(format: "%.4f", cost))", systemImage: "sparkles")
                                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                                    .foregroundColor(.green.opacity(0.8))
                            }
                            if let time = meta.time {
                                Label("\(String(format: "%.1f", time))s", systemImage: "timer")
                                    .font(.system(size: 10, weight: .medium, design: .monospaced))
                                    .foregroundColor(.secondary)
                            }
                        }
                        .padding(.top, 2)
                        .padding(.horizontal, 4)
                    }
                }
            }
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 4)
    }
}

struct BubbleShape: Shape {
    let isCurrent: Bool
    
    func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(roundedRect: rect, byRoundingCorners: [
            .topLeft, .topRight, isCurrent ? .bottomLeft : .bottomRight
        ], cornerRadii: CGSize(width: 18, height: 18))
        return Path(path.cgPath)
    }
}
