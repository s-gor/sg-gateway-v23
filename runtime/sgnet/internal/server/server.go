package server

import (
	"bufio"
	"crypto/rand"
	"crypto/tls"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"strconv"
	"sync"
	"time"

	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/config"
	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/health"
	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/protocol"
	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/relay"
	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/session"
)

const (
	addrIPv4   = 1
	addrDomain = 2
	addrIPv6   = 3
)

type Server struct {
	cfg      config.Config
	registry *session.Registry
	secrets  map[uint64][]byte
	health   *health.State
	listener net.Listener
}

func New(cfg config.Config) (*Server, error) {
	if err := cfg.Validate(); err != nil {
		return nil, err
	}
	secrets := make(map[uint64][]byte)
	for _, d := range cfg.Devices {
		if !d.Enabled {
			continue
		}
		secret, err := d.SecretBytes()
		if err != nil {
			return nil, err
		}
		secrets[d.ID] = secret
	}
	return &Server{
		cfg: cfg, registry: session.NewRegistry(cfg.SessionLimits()),
		secrets: secrets, health: &health.State{StartedAt: time.Now()},
	}, nil
}

func (s *Server) Serve() error {
	cert, err := tls.LoadX509KeyPair(s.cfg.TLS.Certificate, s.cfg.TLS.PrivateKey)
	if err != nil {
		return err
	}
	base, err := net.Listen("tcp", s.cfg.Listen)
	if err != nil {
		return err
	}
	s.listener = tls.NewListener(base, &tls.Config{
		Certificates: []tls.Certificate{cert},
		MinVersion: tls.VersionTLS13,
		MaxVersion: tls.VersionTLS13,
	})
	if s.cfg.HealthSocket != "" {
		if err := os.MkdirAll(dirOf(s.cfg.HealthSocket), 0o750); err != nil {
			_ = s.listener.Close()
			return err
		}
		closeHealth, err := health.ServeUnix(s.cfg.HealthSocket, s.cfg.Listen, s.health)
		if err != nil {
			_ = s.listener.Close()
			return err
		}
		defer closeHealth()
	}
	for {
		conn, err := s.listener.Accept()
		if err != nil {
			return err
		}
		go s.handle(conn)
	}
}

func (s *Server) Close() error {
	if s.listener == nil {
		return nil
	}
	return s.listener.Close()
}

func dirOf(path string) string {
	if i := len(path)-1; i >= 0 {
		for ; i >= 0; i-- {
			if path[i] == '/' {
				if i == 0 { return "/" }
				return path[:i]
			}
		}
	}
	return "."
}

type framedConn struct {
	conn net.Conn
	r    *bufio.Reader
	mu   sync.Mutex
}

func newFramedConn(c net.Conn) *framedConn { return &framedConn{conn: c, r: bufio.NewReader(c)} }

func (f *framedConn) readFrame() (protocol.Header, []byte, error) {
	raw := make([]byte, protocol.HeaderSize)
	if _, err := io.ReadFull(f.r, raw); err != nil {
		return protocol.Header{}, nil, err
	}
	h, err := protocol.DecodeHeader(raw)
	if err != nil {
		return protocol.Header{}, nil, err
	}
	payload := make([]byte, h.Length)
	if _, err := io.ReadFull(f.r, payload); err != nil {
		return protocol.Header{}, nil, err
	}
	return h, payload, nil
}

func (f *framedConn) writeFrame(typ protocol.FrameType, flags uint16, streamID uint32, payload []byte) error {
	if len(payload) > int(protocol.MaxFramePayload) {
		return protocol.ErrFrameTooLarge
	}
	h := protocol.Header{Version: protocol.ProtocolMajor, Type: typ, Flags: flags, StreamID: streamID, Length: uint32(len(payload))}
	raw, err := protocol.EncodeHeader(h)
	if err != nil { return err }
	f.mu.Lock()
	defer f.mu.Unlock()
	if _, err := f.conn.Write(raw[:]); err != nil { return err }
	if len(payload) > 0 {
		_, err = f.conn.Write(payload)
	}
	return err
}

func (s *Server) handle(c net.Conn) {
	defer c.Close()
	if tc, ok := c.(*tls.Conn); ok {
		_ = tc.SetDeadline(time.Now().Add(s.cfg.SessionLimits().HandshakeTimeout))
		if err := tc.Handshake(); err != nil {
			s.health.AuthFailures.Add(1)
			return
		}
	}
	f := newFramedConn(c)
	var serverNonce [32]byte
	if _, err := rand.Read(serverNonce[:]); err != nil { return }
	if err := f.writeFrame(protocol.FrameAuth, 0, 0, serverNonce[:]); err != nil { return }
	h, payload, err := f.readFrame()
	if err != nil || h.Type != protocol.FrameAuth || h.StreamID != 0 || len(payload) != 72 {
		s.health.AuthFailures.Add(1); return
	}
	deviceID := binary.BigEndian.Uint64(payload[:8])
	secret := s.secrets[deviceID]
	if len(secret) == 0 { s.health.AuthFailures.Add(1); return }
	var clientNonce [32]byte
	copy(clientNonce[:], payload[8:40])
	sess, err := s.registry.Authenticate(deviceID, clientNonce, serverNonce, payload[40:72], secret)
	if err != nil { s.health.AuthFailures.Add(1); return }
	s.health.Sessions.Add(1)
	defer s.health.Sessions.Add(-1)
	if tc, ok := c.(*tls.Conn); ok { _ = tc.SetDeadline(time.Time{}) }
	if err := f.writeFrame(protocol.FrameAuthOK, 0, 0, sess.ID[:]); err != nil { return }

	streams := make(map[uint32]net.Conn)
	var streamsMu sync.Mutex
	defer func() {
		streamsMu.Lock()
		defer streamsMu.Unlock()
		for _, conn := range streams { _ = conn.Close() }
	}()
	for {
		h, payload, err = f.readFrame()
		if err != nil { return }
		switch h.Type {
		case protocol.FrameOpen:
			host, port, err := parseDestination(payload)
			if err != nil || h.StreamID == 0 { _ = f.writeFrame(protocol.FrameError, 0, h.StreamID, []byte("open")); continue }
			if err := sess.OpenStream(); err != nil { _ = f.writeFrame(protocol.FrameError, 0, h.StreamID, []byte("limit")); continue }
			upstream, err := relay.DialTCP(host, port)
			if err != nil { sess.CloseStream(); _ = f.writeFrame(protocol.FrameError, 0, h.StreamID, []byte("dial")); continue }
			streamsMu.Lock(); streams[h.StreamID] = upstream; streamsMu.Unlock()
			s.health.Streams.Add(1)
			go func(id uint32, upstream net.Conn) {
				buf := make([]byte, 32*1024)
				for {
					n, er := upstream.Read(buf)
					if n > 0 {
						if wr := f.writeFrame(protocol.FrameData, 0, id, buf[:n]); wr != nil { break }
					}
					if er != nil {
						_ = f.writeFrame(protocol.FrameClose, 0, id, nil)
						break
					}
				}
				streamsMu.Lock()
				if streams[id] == upstream { delete(streams, id) }
				streamsMu.Unlock()
				_ = upstream.Close()
				sess.CloseStream()
				s.health.Streams.Add(-1)
			}(h.StreamID, upstream)
		case protocol.FrameData:
			streamsMu.Lock(); upstream := streams[h.StreamID]; streamsMu.Unlock()
			if upstream == nil { _ = f.writeFrame(protocol.FrameError, 0, h.StreamID, []byte("stream")); continue }
			if _, err := upstream.Write(payload); err != nil { _ = upstream.Close() }
		case protocol.FrameClose:
			streamsMu.Lock(); upstream := streams[h.StreamID]; delete(streams, h.StreamID); streamsMu.Unlock()
			if upstream != nil { _ = upstream.Close() }
		case protocol.FrameDatagram:
			host, port, data, err := parseDatagram(payload)
			if err != nil { _ = f.writeFrame(protocol.FrameError, 0, h.StreamID, []byte("datagram")); continue }
			reply, _, err := relay.RoundTripUDP(host, port, data, 5*time.Second)
			if err != nil { _ = f.writeFrame(protocol.FrameError, 0, h.StreamID, []byte("udp")); continue }
			out, err := encodeDatagram(host, port, reply)
			if err == nil { _ = f.writeFrame(protocol.FrameDatagram, 0, h.StreamID, out) }
		case protocol.FramePing:
			_ = f.writeFrame(protocol.FramePong, 0, 0, payload)
		case protocol.FrameGoAway:
			s.registry.BeginDrain(sess.ID); return
		default:
			_ = f.writeFrame(protocol.FrameError, 0, h.StreamID, []byte("frame"))
		}
	}
}

func parseDestination(payload []byte) (string, uint16, error) {
	host, rest, err := parseAddress(payload)
	if err != nil || len(rest) != 2 { return "", 0, errors.New("bad destination") }
	return host, binary.BigEndian.Uint16(rest), nil
}

func parseDatagram(payload []byte) (string, uint16, []byte, error) {
	host, rest, err := parseAddress(payload)
	if err != nil || len(rest) < 2 { return "", 0, nil, errors.New("bad datagram") }
	return host, binary.BigEndian.Uint16(rest[:2]), rest[2:], nil
}

func parseAddress(payload []byte) (string, []byte, error) {
	if len(payload) < 1 { return "", nil, errors.New("missing address") }
	switch payload[0] {
	case addrIPv4:
		if len(payload) < 5 { return "", nil, errors.New("short ipv4") }
		return net.IP(payload[1:5]).String(), payload[5:], nil
	case addrIPv6:
		if len(payload) < 17 { return "", nil, errors.New("short ipv6") }
		return net.IP(payload[1:17]).String(), payload[17:], nil
	case addrDomain:
		if len(payload) < 2 { return "", nil, errors.New("short domain") }
		n := int(payload[1])
		if n == 0 || len(payload) < 2+n { return "", nil, errors.New("bad domain") }
		return string(payload[2:2+n]), payload[2+n:], nil
	default:
		return "", nil, errors.New("unknown address type")
	}
}

func encodeDatagram(host string, port uint16, data []byte) ([]byte, error) {
	var prefix []byte
	if ip := net.ParseIP(host); ip != nil {
		if v4 := ip.To4(); v4 != nil { prefix = append([]byte{addrIPv4}, v4...) } else { prefix = append([]byte{addrIPv6}, ip.To16()...) }
	} else {
		if len(host) == 0 || len(host) > 255 { return nil, errors.New("invalid host") }
		prefix = append([]byte{addrDomain, byte(len(host))}, []byte(host)...)
	}
	var p [2]byte; binary.BigEndian.PutUint16(p[:], port)
	out := append(prefix, p[:]...)
	out = append(out, data...)
	return out, nil
}

func ParsePort(value string) (uint16, error) {
	n, err := strconv.Atoi(value)
	if err != nil || n < 1 || n > 65535 { return 0, fmt.Errorf("invalid port") }
	return uint16(n), nil
}
