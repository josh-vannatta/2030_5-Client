# IEEE 2030.5 EPRI Client — Linux build
#
# Usage:
#   make                          # optimized build
#   make debug                    # debug build with symbols
#   make clean                    # remove build artifacts
#
# Override OpenSSL location if needed (default: /usr):
#   make OPENSSL_PREFIX=/opt/openssl
#
# Note: Linux only. The platform layer uses epoll (linux/platform.c).
# On macOS, use the project Dockerfile for a Linux build environment.

CC            := gcc
OPENSSL_PREFIX ?= /usr
BUILD         := build

BASE_CFLAGS  := -DOPENSSL_TLS -fPIC -I$(OPENSSL_PREFIX)/include
BASE_LDFLAGS := -L$(OPENSSL_PREFIX)/lib -lssl -lcrypto -lpthread -ldl

ifeq ($(MAKECMDGOALS),debug)
CFLAGS  := $(BASE_CFLAGS) -g -O0
else
CFLAGS  := $(BASE_CFLAGS) -Os -ffunction-sections -Wl,--gc-sections \
           -fno-asynchronous-unwind-tables
endif

LDFLAGS := $(BASE_LDFLAGS)

.PHONY: all debug clean

all debug: $(BUILD)/client_test $(BUILD)/csip_test

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/se_core.o: se_core.c | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD)/client_test: client_test.c $(BUILD)/se_core.o
	$(CC) $(CFLAGS) $^ $(LDFLAGS) -o $@

$(BUILD)/csip_test: csip_test.c $(BUILD)/se_core.o
	$(CC) $(CFLAGS) $^ $(LDFLAGS) -o $@

clean:
	rm -rf $(BUILD)
