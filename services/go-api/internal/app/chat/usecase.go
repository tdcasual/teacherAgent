package chat

import (
	"context"

	domainchat "go-api/internal/domain/chat"
)

type MessageJobRepository interface {
	EnqueueMessageJob(ctx context.Context, sessionID, message string) (string, error)
}

type JobEventStream interface {
	Subscribe(ctx context.Context, jobID string) (<-chan domainchat.JobEvent, error)
}

type SendMessageInput struct {
	SessionID string
	Message   string
}

type SendMessageOutput struct {
	JobID string
}

type Usecase struct {
	repo   MessageJobRepository
	stream JobEventStream
}

func NewUsecase(repo MessageJobRepository, stream JobEventStream) Usecase {
	return Usecase{
		repo:   repo,
		stream: stream,
	}
}

func (u Usecase) SendMessage(ctx context.Context, in SendMessageInput) (SendMessageOutput, error) {
	if in.SessionID == "" {
		return SendMessageOutput{}, domainchat.ErrChatSessionRequired
	}
	if in.Message == "" {
		return SendMessageOutput{}, domainchat.ErrChatMessageRequired
	}

	jobID, err := u.repo.EnqueueMessageJob(ctx, in.SessionID, in.Message)
	if err != nil {
		return SendMessageOutput{}, err
	}
	return SendMessageOutput{JobID: jobID}, nil
}

func (u Usecase) StreamJobEvents(ctx context.Context, jobID string) (<-chan domainchat.JobEvent, error) {
	if jobID == "" {
		return nil, domainchat.ErrChatJobIDRequired
	}
	return u.stream.Subscribe(ctx, jobID)
}
