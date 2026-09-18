package health

import (
	"encoding/json"
	"net"
	"os"
	"sync/atomic"
	"time"
)

type State struct {
	StartedAt    time.Time
	Sessions     atomic.Int64
	Streams      atomic.Int64
	AuthFailures atomic.Int64
}

type Snapshot struct {
	RuntimeVersion string `json:"runtime_version"`
	ProtocolVersion int   `json:"protocol_version"`
	Listener        string `json:"listener"`
	ActiveSessions  int64  `json:"active_sessions"`
	ActiveStreams   int64  `json:"active_streams"`
	UptimeSeconds   int64  `json:"uptime_seconds"`
	AuthFailures    int64  `json:"auth_failures"`
}

func (s *State) Snapshot(listener string) Snapshot {
	return Snapshot{
		RuntimeVersion: "0.1.0",
		ProtocolVersion: 1,
		Listener: listener,
		ActiveSessions: s.Sessions.Load(),
		ActiveStreams: s.Streams.Load(),
		UptimeSeconds: int64(time.Since(s.StartedAt).Seconds()),
		AuthFailures: s.AuthFailures.Load(),
	}
}

func ServeUnix(path, listener string, state *State) (func() error, error) {
	_ = os.Remove(path)
	ln, err := net.Listen("unix", path)
	if err != nil {
		return nil, err
	}
	if err := os.Chmod(path, 0o660); err != nil {
		_ = ln.Close()
		return nil, err
	}
	go func() {
		for {
			conn, err := ln.Accept()
			if err != nil {
				return
			}
			_ = json.NewEncoder(conn).Encode(state.Snapshot(listener))
			_ = conn.Close()
		}
	}()
	return ln.Close, nil
}
