package session

import (
	"errors"
	"testing"
	"time"

	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/auth"
)

func proofFor(secret []byte, deviceID uint64, clientNonce, serverNonce [32]byte) []byte {
	proof := auth.ComputeProof(secret, auth.ClientProofInput{
		DeviceID: deviceID, ClientNonce: clientNonce, ServerNonce: serverNonce, ProtocolMajor: 1,
	})
	return proof[:]
}

func nonces(seed byte) ([32]byte, [32]byte) {
	var client, server [32]byte
	for i := range client {
		client[i] = seed + byte(i)
		server[i] = seed ^ byte(i)
	}
	return client, server
}

func TestAuthenticateRejectsWrongProofAndReplay(t *testing.T) {
	r := NewRegistry(DefaultLimits())
	secret := []byte("0123456789abcdef0123456789abcdef")
	client, server := nonces(1)
	if _, err := r.Authenticate(7, client, server, make([]byte, 32), secret); !errors.Is(err, ErrAuthentication) {
		t.Fatalf("wrong proof error = %v", err)
	}
	proof := proofFor(secret, 7, client, server)
	if _, err := r.Authenticate(7, client, server, proof, secret); err != nil {
		t.Fatalf("first auth: %v", err)
	}
	if _, err := r.Authenticate(7, client, server, proof, secret); !errors.Is(err, ErrReplay) {
		t.Fatalf("replay error = %v", err)
	}
}

func TestTwoSessionHandoverOverlapAndThirdRejected(t *testing.T) {
	r := NewRegistry(DefaultLimits())
	secret := []byte("0123456789abcdef0123456789abcdef")
	for seed := byte(1); seed <= 2; seed++ {
		client, server := nonces(seed)
		if _, err := r.Authenticate(9, client, server, proofFor(secret, 9, client, server), secret); err != nil {
			t.Fatalf("session %d: %v", seed, err)
		}
	}
	if got := r.ActiveSessions(9); got != 2 {
		t.Fatalf("active sessions = %d, want 2", got)
	}
	client, server := nonces(3)
	if _, err := r.Authenticate(9, client, server, proofFor(secret, 9, client, server), secret); !errors.Is(err, ErrSessionLimit) {
		t.Fatalf("third session error = %v", err)
	}
}

func TestRevokedDeviceCannotAuthenticateAndExistingDrains(t *testing.T) {
	limits := DefaultLimits()
	limits.DrainGrace = time.Second
	r := NewRegistry(limits)
	now := time.Unix(100, 0)
	r.now = func() time.Time { return now }
	secret := []byte("0123456789abcdef0123456789abcdef")
	client, server := nonces(4)
	s, err := r.Authenticate(11, client, server, proofFor(secret, 11, client, server), secret)
	if err != nil {
		t.Fatal(err)
	}
	r.RevokeDevice(11)
	if err := s.OpenStream(); !errors.Is(err, ErrDraining) {
		t.Fatalf("OpenStream after revoke = %v", err)
	}
	client2, server2 := nonces(5)
	if _, err := r.Authenticate(11, client2, server2, proofFor(secret, 11, client2, server2), secret); !errors.Is(err, ErrRevoked) {
		t.Fatalf("revoked auth = %v", err)
	}
	now = now.Add(time.Second)
	if got := r.ActiveSessions(11); got != 0 {
		t.Fatalf("active sessions after grace = %d", got)
	}
}

func TestStreamLimitAndDrain(t *testing.T) {
	limits := DefaultLimits()
	limits.MaxStreamsPerSession = 2
	limits.DrainGrace = time.Second
	r := NewRegistry(limits)
	now := time.Unix(200, 0)
	r.now = func() time.Time { return now }
	secret := []byte("0123456789abcdef0123456789abcdef")
	client, server := nonces(6)
	s, err := r.Authenticate(13, client, server, proofFor(secret, 13, client, server), secret)
	if err != nil {
		t.Fatal(err)
	}
	if err := s.OpenStream(); err != nil {
		t.Fatal(err)
	}
	if err := s.OpenStream(); err != nil {
		t.Fatal(err)
	}
	if err := s.OpenStream(); !errors.Is(err, ErrStreamLimit) {
		t.Fatalf("third stream = %v", err)
	}
	s.CloseStream()
	if err := s.OpenStream(); err != nil {
		t.Fatalf("stream after close = %v", err)
	}
	r.BeginDrain(s.ID)
	if err := s.OpenStream(); !errors.Is(err, ErrDraining) {
		t.Fatalf("stream while draining = %v", err)
	}
	now = now.Add(time.Second)
	if got := r.ActiveSessions(13); got != 0 {
		t.Fatalf("active after drain grace = %d", got)
	}
}

func TestReplayCacheExpiresBoundedly(t *testing.T) {
	limits := DefaultLimits()
	limits.HandshakeTimeout = time.Second
	limits.DrainGrace = time.Second
	limits.IdleTimeout = time.Second
	r := NewRegistry(limits)
	now := time.Unix(300, 0)
	r.now = func() time.Time { return now }
	secret := []byte("0123456789abcdef0123456789abcdef")
	client, server := nonces(7)
	proof := proofFor(secret, 15, client, server)
	if _, err := r.Authenticate(15, client, server, proof, secret); err != nil {
		t.Fatal(err)
	}
	now = now.Add(3 * time.Second)
	if _, err := r.Authenticate(15, client, server, proof, secret); err != nil {
		t.Fatalf("expired replay entry still blocks auth: %v", err)
	}
}
