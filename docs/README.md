# Documentation

Reference documentation for the IEEE 2030.5 DER Gateway.

## Guides

| Document | Description |
|----------|-------------|
| [architecture.md](architecture.md) | System design, process boundary, data flows, phase roadmap |
| [configuration.md](configuration.md) | Full `gateway.yaml` reference — all fields, types, register maps |
| [development.md](development.md) | Dev setup, build, test workflow, extending protocols |

---

# Diagrams

Mermaid diagrams. All render natively in GitHub and VS Code (with the [Mermaid Preview extension](https://marketplace.visualstudio.com/items?itemName=bierner.markdown-mermaid)).

## Phase Status

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented |
| 🟡 | Partial / stub |
| ⬜ | Planned |

---

## Architecture

Structural diagrams — how the system is composed.

| Diagram | Status | Description |
|---------|--------|-------------|
| [p0_system_overview](architecture/system_overview.mermaid) | ✅ Phase 0–1 | Top-level block diagram: server ↔ C binary ↔ Python ↔ field device |
| [component_map](architecture/component_map.mermaid) | ✅ Phase 0–1 | Python module dependencies and class names |
| [data_model](architecture/data_model.mermaid) | ✅ Phase 0–1 | Data flow: DERState → XML → C binary; EVENT_JSON → DERBridge → Modbus |

---

## Sequence

Interaction diagrams — messages between components over time.

| Diagram | Status | Description |
|---------|--------|-------------|
| [p0_resource_traversal](sequence/2030_5_resource_traversal.mermaid) | 🟡 Phase 0 | EXI-encoded HTTP exchange for DERControlList retrieval |
| [p1_startup_sequence](sequence/startup_sequence.mermaid) | ✅ Phase 1 | Config → read device state → write XML → spawn C binary → event loop |
| [p1_event_default_control](sequence/event_default_control.mermaid) | 🟡 Phase 1 | DefaultDERControl: baseline setpoints applied at startup |
| [p1_event_start_end](sequence/event_start_end.mermaid) | 🟡 Phase 1 | DERControl event start → register writes → event end → relinquish |
| [p2_exi_encoding](sequence/exi_encoding.mermaid) | ⬜ Phase 2+ | EXI encoding layer: struct → binary → TLS → server |
| [p2_tls_packet_exchange](sequence/tls_packet_exchange.mermaid) | ⬜ Phase 2+ | TLS 1.2 handshake: ECDHE key exchange + mutual auth |

---

## Process

Graph diagrams — navigation maps and state flows.

| Diagram | Status | Description |
|---------|--------|-------------|
| [2030_5_resource_traversal](process/2030_5_resource_traversal.mermaid) | 🟡 Phase 0 | Full 2030.5 resource graph: dcap → edev → fsa → derp → derc → DER uploads |

---

## Extending These Diagrams

Each diagram uses `classDef` to color-code nodes by phase:

- **green** (`implStyle`) — implemented and tested
- **yellow** (`partialStyle`) — partial / stub
- **grey** (`plannedStyle`) — planned but not started

To add a new component:
1. Add the node to the relevant diagram with `:::plannedStyle`
2. Update the status table in this README when implemented
