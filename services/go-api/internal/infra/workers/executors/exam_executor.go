package executors

import (
	"context"

	queueinfra "go-api/internal/infra/queue"
)

type ExamExecutor struct{}

func NewExamExecutor() *ExamExecutor {
	return &ExamExecutor{}
}

func (e *ExamExecutor) Execute(_ context.Context, _ queueinfra.Task) error {
	return nil
}
