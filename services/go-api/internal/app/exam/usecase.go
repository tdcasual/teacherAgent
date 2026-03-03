package exam

import (
	"context"

	domainexam "go-api/internal/domain/exam"
)

type JobQueue interface {
	Enqueue(ctx context.Context, kind domainexam.JobType, payload map[string]string) (string, error)
}

type CreateExamParseJobInput struct {
	ResourceID string
}

type CreateExamParseJobOutput struct {
	JobID string
}

type Usecase struct {
	queue JobQueue
}

func NewUsecase(queue JobQueue) Usecase {
	return Usecase{queue: queue}
}

func (u Usecase) CreateExamParseJob(ctx context.Context, in CreateExamParseJobInput) (CreateExamParseJobOutput, error) {
	if in.ResourceID == "" {
		return CreateExamParseJobOutput{}, domainexam.ErrExamResourceRequired
	}

	jobID, err := u.queue.Enqueue(ctx, domainexam.JobTypeExamParse, map[string]string{
		"resource_id": in.ResourceID,
	})
	if err != nil {
		return CreateExamParseJobOutput{}, err
	}

	return CreateExamParseJobOutput{JobID: jobID}, nil
}
