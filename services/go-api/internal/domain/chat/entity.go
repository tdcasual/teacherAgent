package chat

import "errors"

var (
	ErrChatSessionRequired = errors.New("chat session is required")
	ErrChatMessageRequired = errors.New("chat message is required")
	ErrChatJobIDRequired   = errors.New("chat job id is required")
)

type JobEvent struct {
	Event string
	Data  string
}
