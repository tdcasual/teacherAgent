package job

import (
	"testing"

	domainjob "go-api/internal/domain/job"

	"github.com/stretchr/testify/require"
)

func TestStateTransition_InvalidJumpRejected(t *testing.T) {
	machine := NewStateMachine()

	err := machine.Transition(domainjob.StateDone, domainjob.StateRunning)

	require.ErrorIs(t, err, domainjob.ErrJobInvalidTransition)
}

func TestStateTransition_QueuedToRunningAllowed(t *testing.T) {
	machine := NewStateMachine()

	err := machine.Transition(domainjob.StateQueued, domainjob.StateRunning)

	require.NoError(t, err)
}
