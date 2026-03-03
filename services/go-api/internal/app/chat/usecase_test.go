package chat

import (
	"context"
	"errors"
	"testing"

	domainchat "go-api/internal/domain/chat"

	"github.com/stretchr/testify/require"
)

type fakeRepo struct {
	jobID string
	err   error
}

func (f fakeRepo) EnqueueMessageJob(_ context.Context, _ string, _ string) (string, error) {
	return f.jobID, f.err
}

type fakeStream struct {
	events <-chan domainchat.JobEvent
	err    error
}

func (f fakeStream) Subscribe(_ context.Context, _ string) (<-chan domainchat.JobEvent, error) {
	return f.events, f.err
}

func TestSendMessage_ReturnsJobID(t *testing.T) {
	uc := NewUsecase(fakeRepo{jobID: "job-1"}, fakeStream{})

	out, err := uc.SendMessage(context.Background(), SendMessageInput{
		SessionID: "s1",
		Message:   "hello",
	})

	require.NoError(t, err)
	require.Equal(t, "job-1", out.JobID)
}

func TestSendMessage_RequiresSessionID(t *testing.T) {
	uc := NewUsecase(fakeRepo{jobID: "job-1"}, fakeStream{})

	_, err := uc.SendMessage(context.Background(), SendMessageInput{
		SessionID: "",
		Message:   "hello",
	})

	require.ErrorIs(t, err, domainchat.ErrChatSessionRequired)
}

func TestSendMessage_PropagatesRepoError(t *testing.T) {
	uc := NewUsecase(fakeRepo{err: errors.New("db unavailable")}, fakeStream{})

	_, err := uc.SendMessage(context.Background(), SendMessageInput{
		SessionID: "s1",
		Message:   "hello",
	})

	require.ErrorContains(t, err, "db unavailable")
}

func TestStreamJobEvents_RequiresJobID(t *testing.T) {
	uc := NewUsecase(fakeRepo{jobID: "job-1"}, fakeStream{})

	_, err := uc.StreamJobEvents(context.Background(), "")

	require.ErrorIs(t, err, domainchat.ErrChatJobIDRequired)
}
