package job

import domainjob "go-api/internal/domain/job"

type StateMachine struct{}

func NewStateMachine() StateMachine {
	return StateMachine{}
}

func (m StateMachine) Transition(from, to domainjob.State) error {
	return domainjob.ValidateTransition(from, to)
}
