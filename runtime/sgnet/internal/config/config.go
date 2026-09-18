package config

import (
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"time"

	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/session"
)

type TLSConfig struct {
	ServerName  string `json:"server_name"`
	Certificate string `json:"certificate"`
	PrivateKey  string `json:"private_key"`
	MinVersion  string `json:"min_version"`
}

type Limits struct {
	MaxSessionsPerDevice    int `json:"max_sessions_per_device"`
	MaxStreamsPerSession    int `json:"max_streams_per_session"`
	MaxFramePayload         int `json:"max_frame_payload"`
	HandshakeTimeoutSeconds int `json:"handshake_timeout_seconds"`
	IdleTimeoutSeconds      int `json:"idle_timeout_seconds"`
	DrainGraceSeconds       int `json:"drain_grace_seconds"`
}

type Device struct {
	ID      uint64 `json:"id"`
	Secret  string `json:"secret"`
	Enabled bool   `json:"enabled"`
}

type Config struct {
	Version      int       `json:"version"`
	Listen       string    `json:"listen"`
	TLS          TLSConfig `json:"tls"`
	HealthSocket string    `json:"health_socket"`
	Limits       Limits    `json:"limits"`
	Devices      []Device  `json:"devices"`
}

func Load(path string) (Config, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Config{}, err
	}
	var cfg Config
	if err := json.Unmarshal(raw, &cfg); err != nil {
		return Config{}, err
	}
	if err := cfg.Validate(); err != nil {
		return Config{}, err
	}
	return cfg, nil
}

func (c Config) Validate() error {
	if c.Version != 1 {
		return fmt.Errorf("unsupported config version %d", c.Version)
	}
	host, port, err := net.SplitHostPort(c.Listen)
	if err != nil || port == "" {
		return errors.New("invalid listen address")
	}
	ip := net.ParseIP(host)
	if ip == nil || !ip.IsLoopback() {
		return errors.New("sgnet listener must be loopback-only")
	}
	if c.TLS.ServerName == "" || c.TLS.Certificate == "" || c.TLS.PrivateKey == "" {
		return errors.New("tls server_name/certificate/private_key are required")
	}
	if c.TLS.MinVersion != "" && c.TLS.MinVersion != "1.3" {
		return errors.New("sgnet requires tls 1.3")
	}
	for _, d := range c.Devices {
		if d.ID == 0 {
			return errors.New("device id must be non-zero")
		}
		if d.Enabled {
			secret, err := d.SecretBytes()
			if err != nil || len(secret) < 32 {
				return fmt.Errorf("device %d has invalid secret", d.ID)
			}
		}
	}
	return nil
}

func (d Device) SecretBytes() ([]byte, error) {
	return base64.RawURLEncoding.DecodeString(d.Secret)
}

func (c Config) SessionLimits() session.Limits {
	return session.Limits{
		MaxSessionsPerDevice: c.Limits.MaxSessionsPerDevice,
		MaxStreamsPerSession: c.Limits.MaxStreamsPerSession,
		HandshakeTimeout: time.Duration(c.Limits.HandshakeTimeoutSeconds) * time.Second,
		IdleTimeout: time.Duration(c.Limits.IdleTimeoutSeconds) * time.Second,
		DrainGrace: time.Duration(c.Limits.DrainGraceSeconds) * time.Second,
	}
}
