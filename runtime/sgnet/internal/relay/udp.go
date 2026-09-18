package relay

import (
	"fmt"
	"net"
	"time"
)

func RoundTripUDP(host string, port uint16, payload []byte, timeout time.Duration) ([]byte, net.Addr, error) {
	conn, err := net.Dial("udp", net.JoinHostPort(host, fmt.Sprintf("%d", port)))
	if err != nil {
		return nil, nil, err
	}
	defer conn.Close()
	if err := conn.SetDeadline(time.Now().Add(timeout)); err != nil {
		return nil, nil, err
	}
	if _, err := conn.Write(payload); err != nil {
		return nil, nil, err
	}
	buf := make([]byte, 64*1024)
	n, err := conn.Read(buf)
	if err != nil {
		return nil, nil, err
	}
	return buf[:n], conn.RemoteAddr(), nil
}
