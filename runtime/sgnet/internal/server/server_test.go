package server

import (
	"encoding/binary"
	"net"
	"testing"

	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/config"
)

func TestConfigRejectsPublicListener(t *testing.T) {
	cfg := config.Config{
		Version: 1, Listen: "0.0.0.0:10448",
		TLS: config.TLSConfig{ServerName: "example.com", Certificate: "/x", PrivateKey: "/y", MinVersion: "1.3"},
	}
	if err := cfg.Validate(); err == nil {
		t.Fatal("public SG-Net listener accepted")
	}
}

func TestDestinationParsingIPv4(t *testing.T) {
	raw := []byte{addrIPv4, 127, 0, 0, 1, 0x01, 0xbb}
	host, port, err := parseDestination(raw)
	if err != nil || host != "127.0.0.1" || port != 443 {
		t.Fatalf("got host=%q port=%d err=%v", host, port, err)
	}
}

func TestDestinationParsingDomain(t *testing.T) {
	host := "example.com"
	raw := append([]byte{addrDomain, byte(len(host))}, []byte(host)...)
	var p [2]byte
	binary.BigEndian.PutUint16(p[:], 8443)
	raw = append(raw, p[:]...)
	got, port, err := parseDestination(raw)
	if err != nil || got != host || port != 8443 {
		t.Fatalf("got host=%q port=%d err=%v", got, port, err)
	}
}

func TestDestinationParsingIPv6(t *testing.T) {
	ip := net.ParseIP("2001:db8::1").To16()
	raw := append([]byte{addrIPv6}, ip...)
	raw = append(raw, 0x01, 0xbb)
	host, port, err := parseDestination(raw)
	if err != nil || net.ParseIP(host) == nil || port != 443 {
		t.Fatalf("got host=%q port=%d err=%v", host, port, err)
	}
}

func FuzzParseDestination(f *testing.F) {
	f.Add([]byte{addrIPv4, 127, 0, 0, 1, 0, 80})
	f.Add([]byte{addrDomain, 1, 'a', 0, 53})
	f.Fuzz(func(t *testing.T, raw []byte) {
		_, _, _ = parseDestination(raw)
	})
}
