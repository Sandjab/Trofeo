// CLI TrofeoKit — point d'entrée (étoffé après Transport/Render).

import TrofeoKit

let initPkt = TrofeoProtocol.buildInitPacket()
print("TrofeoKit — init packet \(initPkt.count) o, magic \(initPkt[0..<4].map { String(format: "%02x", $0) }.joined())")
