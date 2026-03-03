package assignment

import "errors"

type DraftStatus string

const (
	DraftStatusSaved  DraftStatus = "saved"
	DraftStatusQueued DraftStatus = "queued"
)

var ErrAssignmentInvalidState = errors.New("assignment invalid state")
