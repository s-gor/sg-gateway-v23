package protocol

import (
	"encoding/binary"
	"errors"
	"fmt"
)

const (
	ProtocolMajor   uint8  = 1
	HeaderSize             = 12
	MaxFramePayload uint32 = 1 << 20
)

type FrameType uint8

const (
	FrameAuth     FrameType = 0x01
	FrameAuthOK   FrameType = 0x02
	FrameOpen     FrameType = 0x10
	FrameData     FrameType = 0x11
	FrameDatagram FrameType = 0x12
	FrameClose    FrameType = 0x13
	FramePing     FrameType = 0x20
	FramePong     FrameType = 0x21
	FrameGoAway   FrameType = 0x22
	FrameError    FrameType = 0x23
)

var (
	ErrShortHeader        = errors.New("sgnet: short frame header")
	ErrUnsupportedVersion = errors.New("sgnet: unsupported protocol version")
	ErrUnknownFrameType   = errors.New("sgnet: unknown frame type")
	ErrFrameTooLarge      = errors.New("sgnet: frame payload too large")
)

type Header struct {
	Version  uint8
	Type     FrameType
	Flags    uint16
	StreamID uint32
	Length   uint32
}

func validFrameType(t FrameType) bool {
	switch t {
	case FrameAuth, FrameAuthOK, FrameOpen, FrameData, FrameDatagram, FrameClose, FramePing, FramePong, FrameGoAway, FrameError:
		return true
	default:
		return false
	}
}

func validateHeader(h Header) error {
	if h.Version != ProtocolMajor {
		return fmt.Errorf("%w: %d", ErrUnsupportedVersion, h.Version)
	}
	if !validFrameType(h.Type) {
		return fmt.Errorf("%w: 0x%02x", ErrUnknownFrameType, uint8(h.Type))
	}
	if h.Length > MaxFramePayload {
		return fmt.Errorf("%w: %d", ErrFrameTooLarge, h.Length)
	}
	return nil
}

func EncodeHeader(h Header) ([HeaderSize]byte, error) {
	var raw [HeaderSize]byte
	if err := validateHeader(h); err != nil {
		return raw, err
	}
	raw[0] = h.Version
	raw[1] = byte(h.Type)
	binary.BigEndian.PutUint16(raw[2:4], h.Flags)
	binary.BigEndian.PutUint32(raw[4:8], h.StreamID)
	binary.BigEndian.PutUint32(raw[8:12], h.Length)
	return raw, nil
}

func DecodeHeader(raw []byte) (Header, error) {
	if len(raw) < HeaderSize {
		return Header{}, ErrShortHeader
	}
	h := Header{
		Version:  raw[0],
		Type:     FrameType(raw[1]),
		Flags:    binary.BigEndian.Uint16(raw[2:4]),
		StreamID: binary.BigEndian.Uint32(raw[4:8]),
		Length:   binary.BigEndian.Uint32(raw[8:12]),
	}
	if err := validateHeader(h); err != nil {
		return Header{}, err
	}
	return h, nil
}
