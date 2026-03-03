package db

import (
	"context"

	domainchat "go-api/internal/domain/chat"
)

type ChatRepoPG struct{}

func NewChatRepoPG() *ChatRepoPG {
	return &ChatRepoPG{}
}

func (r *ChatRepoPG) EnqueueMessageJob(_ context.Context, _ string, _ string) (string, error) {
	return "chat-job-1", nil
}

func (r *ChatRepoPG) Subscribe(_ context.Context, _ string) (<-chan domainchat.JobEvent, error) {
	ch := make(chan domainchat.JobEvent, 1)
	ch <- domainchat.JobEvent{Event: "done", Data: "ok"}
	close(ch)
	return ch, nil
}
