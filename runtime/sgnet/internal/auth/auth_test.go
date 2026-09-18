package auth

import (
	"encoding/hex"
	"testing"
)

func testInput() ClientProofInput {
	var client [32]byte
	var server [32]byte
	for i := range client {
		client[i] = byte(i)
		server[i] = byte(255 - i)
	}
	return ClientProofInput{
		DeviceID:      0x0102030405060708,
		ClientNonce:   client,
		ServerNonce:   server,
		ProtocolMajor: 1,
	}
}

func TestComputeProofGoldenVector(t *testing.T) {
	got := ComputeProof([]byte("0123456789abcdef0123456789abcdef"), testInput())
	const want = "REPLACE_ME"
	if hex.EncodeToString(got[:]) == want {
		return
	}
	// This guard intentionally exposes the deterministic value when the vector
	// is first frozen. Replace want with the emitted digest and keep it fixed.
	t.Fatalf("proof = %x; freeze this digest as the golden vector", got)
}

func TestVerifyProof(t *testing.T) {
	secret := []byte("0123456789abcdef0123456789abcdef")
	in := testInput()
	proof := ComputeProof(secret, in)
	if !VerifyProof(secret, in, proof[:]) {
		t.Fatal("valid proof rejected")
	}
	proof[0] ^= 0xff
	if VerifyProof(secret, in, proof[:]) {
		t.Fatal("modified proof accepted")
	}
}

func TestProofBindsNoncesAndDevice(t *testing.T) {
	secret := []byte("0123456789abcdef0123456789abcdef")
	base := testInput()
	want := ComputeProof(secret, base)

	changed := base
	changed.DeviceID++
	if got := ComputeProof(secret, changed); got == want {
		t.Fatal("proof did not bind device id")
	}
	changed = base
	changed.ClientNonce[0] ^= 1
	if got := ComputeProof(secret, changed); got == want {
		t.Fatal("proof did not bind client nonce")
	}
	changed = base
	changed.ServerNonce[0] ^= 1
	if got := ComputeProof(secret, changed); got == want {
		t.Fatal("proof did not bind server nonce")
	}
}
