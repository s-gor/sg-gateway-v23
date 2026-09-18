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
	const want = "06d71223906711af97a561f625e095228c2b90a739db9499e317df4d22fc2887"
	if encoded := hex.EncodeToString(got[:]); encoded != want {
		t.Fatalf("proof = %s, want %s", encoded, want)
	}
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
