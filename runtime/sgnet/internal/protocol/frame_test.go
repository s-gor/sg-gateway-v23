package protocol

import (
	"encoding/hex"
	"errors"
	"testing"
)

func TestHeaderGoldenVectors(t *testing.T) {
	types := []FrameType{
		FrameAuth, FrameAuthOK, FrameOpen, FrameData, FrameDatagram,
		FrameClose, FramePing, FramePong, FrameGoAway, FrameError,
	}
	for _, typ := range types {
		t.Run(hex.EncodeToString([]byte{byte(typ)}), func(t *testing.T) {
			in := Header{
				Version:  ProtocolMajor,
				Type:     typ,
				Flags:    0x1234,
				StreamID: 0x01020304,
				Length:   0x00010203,
			}
			raw, err := EncodeHeader(in)
			if err != nil {
				t.Fatalf("EncodeHeader() error = %v", err)
			}
			wantPrefix := []byte{0x01, byte(typ), 0x12, 0x34, 0x01, 0x02, 0x03, 0x04, 0x00, 0x01, 0x02, 0x03}
			if string(raw[:]) != string(wantPrefix) {
				t.Fatalf("encoded = %x, want %x", raw, wantPrefix)
			}
			out, err := DecodeHeader(raw[:])
			if err != nil {
				t.Fatalf("DecodeHeader() error = %v", err)
			}
			if out != in {
				t.Fatalf("round trip = %#v, want %#v", out, in)
			}
		})
	}
}

func TestHeaderAcceptsMaximumPayload(t *testing.T) {
	h := Header{Version: ProtocolMajor, Type: FrameData, StreamID: 7, Length: MaxFramePayload}
	raw, err := EncodeHeader(h)
	if err != nil {
		t.Fatalf("EncodeHeader() error = %v", err)
	}
	if _, err := DecodeHeader(raw[:]); err != nil {
		t.Fatalf("DecodeHeader() error = %v", err)
	}
}

func TestHeaderRejectsOversizedPayload(t *testing.T) {
	_, err := EncodeHeader(Header{Version: ProtocolMajor, Type: FrameData, Length: MaxFramePayload + 1})
	if !errors.Is(err, ErrFrameTooLarge) {
		t.Fatalf("error = %v, want ErrFrameTooLarge", err)
	}
}

func TestHeaderRejectsUnsupportedVersion(t *testing.T) {
	_, err := EncodeHeader(Header{Version: ProtocolMajor + 1, Type: FramePing})
	if !errors.Is(err, ErrUnsupportedVersion) {
		t.Fatalf("error = %v, want ErrUnsupportedVersion", err)
	}
}

func TestHeaderRejectsUnknownFrameType(t *testing.T) {
	_, err := EncodeHeader(Header{Version: ProtocolMajor, Type: 0xff})
	if !errors.Is(err, ErrUnknownFrameType) {
		t.Fatalf("error = %v, want ErrUnknownFrameType", err)
	}
}

func TestDecodeHeaderRejectsShortInput(t *testing.T) {
	if _, err := DecodeHeader(make([]byte, HeaderSize-1)); !errors.Is(err, ErrShortHeader) {
		t.Fatalf("error = %v, want ErrShortHeader", err)
	}
}
