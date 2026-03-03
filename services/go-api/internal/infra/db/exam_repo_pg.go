package db

import (
	"context"
	"fmt"

	domainexam "go-api/internal/domain/exam"
)

type ExamQueuePG struct{}

func NewExamQueuePG() *ExamQueuePG {
	return &ExamQueuePG{}
}

func (q *ExamQueuePG) Enqueue(_ context.Context, kind domainexam.JobType, payload map[string]string) (string, error) {
	return fmt.Sprintf("%s:%s", kind, payload["resource_id"]), nil
}
