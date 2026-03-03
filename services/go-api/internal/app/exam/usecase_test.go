package exam

import (
	"context"
	"errors"
	"testing"

	domainexam "go-api/internal/domain/exam"

	"github.com/stretchr/testify/require"
)

type fakeQueue struct {
	jobID string
	err   error
	kind  domainexam.JobType
}

func (f *fakeQueue) Enqueue(_ context.Context, kind domainexam.JobType, _ map[string]string) (string, error) {
	f.kind = kind
	return f.jobID, f.err
}

func TestCreateExamJob_ReturnsQueuedJobID(t *testing.T) {
	queue := &fakeQueue{jobID: "job-1"}
	uc := NewUsecase(queue)

	out, err := uc.CreateExamParseJob(context.Background(), CreateExamParseJobInput{
		ResourceID: "res-1",
	})

	require.NoError(t, err)
	require.Equal(t, "job-1", out.JobID)
	require.Equal(t, domainexam.JobTypeExamParse, queue.kind)
}

func TestCreateExamJob_RequiresResourceID(t *testing.T) {
	queue := &fakeQueue{jobID: "unused"}
	uc := NewUsecase(queue)

	_, err := uc.CreateExamParseJob(context.Background(), CreateExamParseJobInput{})

	require.ErrorIs(t, err, domainexam.ErrExamResourceRequired)
}

func TestCreateExamJob_PropagatesQueueError(t *testing.T) {
	queue := &fakeQueue{err: errors.New("queue unavailable")}
	uc := NewUsecase(queue)

	_, err := uc.CreateExamParseJob(context.Background(), CreateExamParseJobInput{
		ResourceID: "res-1",
	})

	require.ErrorContains(t, err, "queue unavailable")
}
