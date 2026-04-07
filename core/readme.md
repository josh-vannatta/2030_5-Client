IEEE 2030.5 Client
==================

A C library and application framework for IEEE 2030.5 (Smart Energy Profile 2) compliant applications. Lightweight, portable, and event-driven (state machines + async events).

Features
--------

- Portable networking layer (UDP, TCP, IPv6/IPv4)
- Linux platform support
- TLS 1.2 via OpenSSL
- DNS-SD client for IEEE 2030.5 service discovery
- HTTP/1.1 client/server
- XML/EXI schema-based parser and serializer (order-tolerant, 2018 namespace)
- IEEE 2030.5 DER function set client API

Dependencies
------------

- GCC 4.6 or greater
- OpenSSL 1.1.0 or greater
- GNU Bash

Building
--------

```bash
./build.sh          # optimized (default)
./build.sh debug    # debug build (-g)
./build.sh cross    # cross-compile (edit linux_cross_host/linux_cross_prefix in build.sh first)
```

The binary is output to `build/client_test`.

Running the Client
------------------

### Syntax

```
./build/client_test <interface> [device_cert [ca_certs...]] <subtype[:1][/path] | URI> [commands]
```

| Argument | Description |
|----------|-------------|
| `interface` | Network interface name (e.g. `eth0`, `lo`) |
| `device_cert` | Path to device certificate (PEM or ASN1). Required for TLS. |
| `ca_certs` | CA certificate file(s) or directory. Defaults to `./certs` if not specified. |
| `subtype` | DNS-SD subtype to discover (e.g. `s2`) |
| `URI` | Direct server URI (e.g. `http://192.168.1.1/sep2`) |

### Commands

Commands can be combined. They are processed left to right.

| Command | Description |
|---------|-------------|
| `edev` | Fetch the EndDevice list and FSA (Function Set Assignments) |
| `register` | Register device — GETs Registration resource and PUTs DER settings from `./settings/` |
| `pin <PIN>` | In-bound registration — PUT the provided PIN to the server |
| `fsa` | Full FSA retrieval (EndDevice, FSA, DERPrograms, Time) plus registration |
| `all` | Full retrieval: EndDevice, FSA, DER programs/controls, Time, registration, scheduling, and settings |
| `primary` | Same as `all`, marks this client as the primary device |
| `time` | Fetch and synchronize server time only |
| `self` | Fetch the SelfDevice resource |
| `subscribe` | Subscribe to EndDevice and FSA resources |
| `metering` | Full retrieval (`all`) plus meter reading uploads |
| `meter` | Fetch EndDevice list and run meter test |
| `alarm` | Full retrieval (`all`) plus alarm test |
| `device <dir>` | Load device certificates from `<dir>` and validate EndDevice list |
| `load <SFDI> <dir>` | Load DER settings for `<SFDI>` from `<dir>` |
| `delete <SFDI>` | Delete the managed EndDevice with the given SFDI |
| `poll <seconds>` | Set the active event poll interval in seconds |
| `sfdi <SFDI>` | Override the client SFDI (used when no device certificate is provided) |
| `inverter` | Run in inverter mode (filters EndDevices by device SFDI) |

### Examples

```bash
# Discover server via DNS-SD on eth0, no TLS, fetch EndDevice list
./build/client_test eth0 s2 edev

# Connect directly to server, TLS, register device
./build/client_test eth0 device.pem certs/ http://192.168.1.100/sep2 register

# Full retrieval with scheduling
./build/client_test eth0 device.pem certs/ http://192.168.1.100/sep2 all

# Register with explicit PIN (in-bound registration)
./build/client_test eth0 device.pem certs/ http://192.168.1.100/sep2 register pin 111115

# Get server time only
./build/client_test eth0 http://192.168.1.100/sep2 time

# Fetch FSA and subscribe
./build/client_test eth0 device.pem certs/ http://192.168.1.100/sep2 fsa subscribe

# Load DER settings for a specific device SFDI
./build/client_test eth0 device.pem certs/ http://192.168.1.100/sep2 load 123456789 settings/
```

Settings
--------

When using `register`, `all`, `metering`, or `load`, the client reads DER settings from XML files in the `settings/` directory:

- `DERAvailability.xml`
- `DERCapability.xml`
- `DERSettings.xml`
- `DERStatus.xml`

Branching Strategy
------------------

All contributions must follow this branching model strictly:

```
feature/sbx  →  develop  →  main  →  master
```

| Branch | Purpose |
|--------|---------|
| `feature/<name>` or `sbx/<name>` | Individual feature or sandbox work. Branch off from `develop`. |
| `develop` | Integration branch. All features are merged here first. |
| `main` | Stable, tested code. Merged from `develop` after review. |
| `master` | Production-ready releases only. Merged from `main`. |

**Rules:**
- Never commit directly to `main` or `master`
- Never merge `feature`/`sbx` branches directly into `main` or `master`
- All merges into `develop` require a pull request
- All merges into `main` and `master` require a pull request with review
- Delete feature/sbx branches after merging into `develop`
