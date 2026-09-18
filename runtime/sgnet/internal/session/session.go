package session

import (
	"crypto/rand"
	"errors"
	"sync"
	"time"

	"github.com/s-gor/sg-gateway-v23/runtime/sgnet/internal/auth"
)

var (
	ErrAuthentication = errors.New("sgnet: authentication failed")
	ErrReplay         = errors.New("sgnet: replay detected")
	ErrRevoked        = errors.New("sgnet: device revoked")
	ErrSessionLimit   = errors.New("sgnet: session limit reached")
	ErrStreamLimit    = errors.New("sgnet: stream limit reached")
	ErrDraining       = errors.New("sgnet: session draining")
)

type Limits struct {
	MaxSessionsPerDevice int
	MaxStreamsPerSession int
	HandshakeTimeout     time.Duration
	IdleTimeout          time.Duration
	DrainGrace           time.Duration
}

func DefaultLimits() Limits {
	return Limits{
		MaxSessionsPerDevice: 2,
		MaxStreamsPerSession: 512,
		HandshakeTimeout:     10 * time.Second,
		IdleTimeout:          120 * time.Second,
		DrainGrace:           15 * time.Second,
	}
}

type sessionState struct {
	id         [16]byte
	deviceID   uint64
	createdAt  time.Time
	lastActive time.Time
	drainingAt time.Time
	streams    int
}

type Session struct {
	ID       [16]byte
	DeviceID uint64
	registry *Registry
}

type replayKey struct {
	deviceID uint64
	nonce    [32]byte
}

type Registry struct {
	mu       sync.Mutex
	limits   Limits
	sessions map[[16]byte]*sessionState
	byDevice map[uint64]map[[16]byte]struct{}
	replay   map[replayKey]time.Time
	revoked  map[uint64]struct{}
	now      func() time.Time
}

func NewRegistry(limits Limits) *Registry {
	defaults := DefaultLimits()
	if limits.MaxSessionsPerDevice <= 0 {
		limits.MaxSessionsPerDevice = defaults.MaxSessionsPerDevice
	}
	if limits.MaxStreamsPerSession <= 0 {
		limits.MaxStreamsPerSession = defaults.MaxStreamsPerSession
	}
	if limits.HandshakeTimeout <= 0 {
		limits.HandshakeTimeout = defaults.HandshakeTimeout
	}
	if limits.IdleTimeout <= 0 {
		limits.IdleTimeout = defaults.IdleTimeout
	}
	if limits.DrainGrace <= 0 {
		limits.DrainGrace = defaults.DrainGrace
	}
	return &Registry{
		limits:   limits,
		sessions: make(map[[16]byte]*sessionState),
		byDevice: make(map[uint64]map[[16]byte]struct{}),
		replay:   make(map[replayKey]time.Time),
		revoked:  make(map[uint64]struct{}),
		now:      time.Now,
	}
}

func (r *Registry) cleanupLocked(now time.Time) {
	for id, state := range r.sessions {
		expiredIdle := now.Sub(state.lastActive) > r.limits.IdleTimeout
		expiredDrain := !state.drainingAt.IsZero() && now.Sub(state.drainingAt) >= r.limits.DrainGrace
		if expiredIdle || expiredDrain {
			r.removeSessionLocked(id, state.deviceID)
		}
	}
	replayWindow := r.limits.HandshakeTimeout + r.limits.DrainGrace
	for key, seen := range r.replay {
		if now.Sub(seen) > replayWindow {
			delete(r.replay, key)
		}
	}
}

func (r *Registry) removeSessionLocked(id [16]byte, deviceID uint64) {
	delete(r.sessions, id)
	if rows := r.byDevice[deviceID]; rows != nil {
		delete(rows, id)
		if len(rows) == 0 {
			delete(r.byDevice, deviceID)
		}
	}
}

func (r *Registry) Authenticate(deviceID uint64, clientNonce, serverNonce [32]byte, proof []byte, secret []byte) (Session, error) {
	r.mu.Lock()
	defer r.mu.Unlock()

	now := r.now()
	r.cleanupLocked(now)
	if _, ok := r.revoked[deviceID]; ok {
		return Session{}, ErrRevoked
	}

	replay := replayKey{deviceID: deviceID, nonce: clientNonce}
	if _, ok := r.replay[replay]; ok {
		return Session{}, ErrReplay
	}
	input := auth.ClientProofInput{
		DeviceID:      deviceID,
		ClientNonce:   clientNonce,
		ServerNonce:   serverNonce,
		ProtocolMajor: 1,
	}
	if !auth.VerifyProof(secret, input, proof) {
		return Session{}, ErrAuthentication
	}
	if len(r.byDevice[deviceID]) >= r.limits.MaxSessionsPerDevice {
		return Session{}, ErrSessionLimit
	}

	var id [16]byte
	if _, err := rand.Read(id[:]); err != nil {
		return Session{}, err
	}
	state := &sessionState{
		id:         id,
		deviceID:   deviceID,
		createdAt:  now,
		lastActive: now,
	}
	r.sessions[id] = state
	if r.byDevice[deviceID] == nil {
		r.byDevice[deviceID] = make(map[[16]byte]struct{})
	}
	r.byDevice[deviceID][id] = struct{}{}
	r.replay[replay] = now
	return Session{ID: id, DeviceID: deviceID, registry: r}, nil
}

func (r *Registry) RevokeDevice(deviceID uint64) {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.revoked[deviceID] = struct{}{}
	now := r.now()
	for id := range r.byDevice[deviceID] {
		if state := r.sessions[id]; state != nil && state.drainingAt.IsZero() {
			state.drainingAt = now
		}
	}
}

func (r *Registry) BeginDrain(sessionID [16]byte) {
	r.mu.Lock()
	defer r.mu.Unlock()
	if state := r.sessions[sessionID]; state != nil && state.drainingAt.IsZero() {
		state.drainingAt = r.now()
	}
}

func (r *Registry) ActiveSessions(deviceID uint64) int {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.cleanupLocked(r.now())
	return len(r.byDevice[deviceID])
}

func (s Session) OpenStream() error {
	if s.registry == nil {
		return ErrAuthentication
	}
	r := s.registry
	r.mu.Lock()
	defer r.mu.Unlock()
	r.cleanupLocked(r.now())
	state := r.sessions[s.ID]
	if state == nil {
		return ErrAuthentication
	}
	if !state.drainingAt.IsZero() {
		return ErrDraining
	}
	if state.streams >= r.limits.MaxStreamsPerSession {
		return ErrStreamLimit
	}
	state.streams++
	state.lastActive = r.now()
	return nil
}

func (s Session) CloseStream() {
	if s.registry == nil {
		return
	}
	r := s.registry
	r.mu.Lock()
	defer r.mu.Unlock()
	state := r.sessions[s.ID]
	if state == nil {
		return
	}
	if state.streams > 0 {
		state.streams--
	}
	state.lastActive = r.now()
}
