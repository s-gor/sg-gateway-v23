package relay

import (
	"fmt"
	"io"
	"net"
)

func DialTCP(host string, port uint16) (net.Conn, error) {
	return net.Dial("tcp", net.JoinHostPort(host, fmt.Sprintf("%d", port)))
}

func CopyHalfClose(dst net.Conn, src io.Reader) error {
	_, err := io.Copy(dst, src)
	if tcp, ok := dst.(*net.TCPConn); ok {
		_ = tcp.CloseWrite()
	}
	return err
}
