package queue

import (
	"context"
	"sync"
)

type Task struct {
	Type    string
	Payload map[string]string
}

type RedisQueue struct {
	mu    sync.Mutex
	tasks []Task
}

func NewRedisQueue() *RedisQueue {
	return &RedisQueue{}
}

func (q *RedisQueue) Enqueue(_ context.Context, task Task) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	q.tasks = append(q.tasks, task)
	return nil
}

func (q *RedisQueue) Dequeue(_ context.Context) (Task, bool, error) {
	q.mu.Lock()
	defer q.mu.Unlock()

	if len(q.tasks) == 0 {
		return Task{}, false, nil
	}

	task := q.tasks[0]
	q.tasks = q.tasks[1:]
	return task, true, nil
}
