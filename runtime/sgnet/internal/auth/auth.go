package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/binary"
)

const proofDomain = "SG-NET/1-AUTH"

type ClientProofInput struct {
	DeviceID      uint64
	ClientNonce   [32]byte
	ServerNonce   [32]byte
	ProtocolMajor uint8
}

func transcript(in ClientProofInput) []byte {
	buf := make([]byte, 0, len(proofDomain)+1+8+32+32+1)
	buf = append(buf, byte(len(proofDomain)))
	buf = append(buf, proofDomain...)
	var id [8]byte
	binary.BigEndian.PutUint64(id[:], in.DeviceID)
	buf = append(buf, id[:]...)
	buf = append(buf, in.ClientNonce[:]...)
	buf = append(buf, in.ServerNonce[:]...)
	buf = append(buf, in.ProtocolMajor)
	return buf
}

func ComputeProof(secret []byte, in ClientProofInput) [32]byte {
	mac := hmac.New(sha256.New, secret)
	_, _ = mac.Write(transcript(in))
	var out [32]byte
	copy(out[:], mac.Sum(nil))
	return out
}

func VerifyProof(secret []byte, in ClientProofInput, proof []byte) bool {
	expected := ComputeProof(secret, in)
	return len(proof) == len(expected) && hmac.Equal(expected[:], proof)
}
