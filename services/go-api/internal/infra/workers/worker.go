package workers

import (
	"context"
	"fmt"

	queueinfra "go-api/internal/infra/queue"
)

type Queue interface {
	Dequeue(ctx context.Context) (queueinfra.Task, bool, error)
}

type Executor interface {
	Execute(ctx context.Context, task queueinfra.Task) error
}

type Worker struct {
	queue     Queue
	executors map[string]Executor
}

func NewWorker(queue Queue, executors map[string]Executor) Worker {
	return Worker{
		queue:     queue,
		executors: executors,
	}
}

func (w Worker) RunOnce(ctx context.Context) error {
	task, ok, err := w.queue.Dequeue(ctx)
	if err != nil {
		return err
	}
	if !ok {
		return nil
	}

	exec, ok := w.executors[task.Type]
	if !ok {
		return fmt.Errorf("executor not found for task type: %s", task.Type)
	}

	return exec.Execute(ctx, task)
}
