package executors

import (
	"context"

	queueinfra "go-api/internal/infra/queue"
)

type AssignmentExecutor struct{}

func NewAssignmentExecutor() *AssignmentExecutor {
	return &AssignmentExecutor{}
}

func (e *AssignmentExecutor) Execute(_ context.Context, _ queueinfra.Task) error {
	return nil
}
