package job

import "errors"

type State string

const (
	StateQueued  State = "queued"
	StateRunning State = "running"
	StateDone    State = "done"
	StateFailed  State = "failed"
	StateTimeout State = "timeout"
)

var ErrJobInvalidTransition = errors.New("invalid job state transition")

var allowedTransitions = map[State]map[State]struct{}{
	StateQueued: {
		StateRunning: {},
		StateFailed:  {},
	},
	StateRunning: {
		StateDone:    {},
		StateFailed:  {},
		StateTimeout: {},
	},
}

func ValidateTransition(from, to State) error {
	next, ok := allowedTransitions[from]
	if !ok {
		return ErrJobInvalidTransition
	}
	if _, ok := next[to]; !ok {
		return ErrJobInvalidTransition
	}
	return nil
}
