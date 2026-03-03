package executors

import (
	"context"

	queueinfra "go-api/internal/infra/queue"
)

type ChatExecutor struct{}

func NewChatExecutor() *ChatExecutor {
	return &ChatExecutor{}
}

func (e *ChatExecutor) Execute(_ context.Context, _ queueinfra.Task) error {
	return nil
}
