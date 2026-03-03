package workers

import (
	"context"
	"errors"
	"testing"

	queueinfra "go-api/internal/infra/queue"

	"github.com/stretchr/testify/require"
)

type fakeQueue struct {
	task queueinfra.Task
	ok   bool
	err  error
}

func (f *fakeQueue) Dequeue(_ context.Context) (queueinfra.Task, bool, error) {
	return f.task, f.ok, f.err
}

type fakeExecutor struct {
	called bool
	err    error
}

func (f *fakeExecutor) Execute(_ context.Context, _ queueinfra.Task) error {
	f.called = true
	return f.err
}

func TestRunOnce_ExecutesTaskWithMappedExecutor(t *testing.T) {
	q := &fakeQueue{
		task: queueinfra.Task{Type: "chat"},
		ok:   true,
	}
	exec := &fakeExecutor{}
	worker := NewWorker(q, map[string]Executor{
		"chat": exec,
	})

	err := worker.RunOnce(context.Background())

	require.NoError(t, err)
	require.True(t, exec.called)
}

func TestRunOnce_UnknownExecutorReturnsError(t *testing.T) {
	q := &fakeQueue{
		task: queueinfra.Task{Type: "unknown"},
		ok:   true,
	}
	worker := NewWorker(q, map[string]Executor{})

	err := worker.RunOnce(context.Background())

	require.ErrorContains(t, err, "executor not found")
}

func TestRunOnce_PropagatesQueueError(t *testing.T) {
	q := &fakeQueue{err: errors.New("queue down")}
	worker := NewWorker(q, map[string]Executor{})

	err := worker.RunOnce(context.Background())

	require.ErrorContains(t, err, "queue down")
}
