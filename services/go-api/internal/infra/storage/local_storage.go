package storage

import (
	"context"
	"fmt"

	appfiles "go-api/internal/app/files"
)

type LocalStorage struct{}

var _ appfiles.MetadataStorage = (*LocalStorage)(nil)

func NewLocalStorage() *LocalStorage {
	return &LocalStorage{}
}

func (s *LocalStorage) SaveMetadata(_ context.Context, fileName string, _ int64) (string, error) {
	return fmt.Sprintf("local-%s", fileName), nil
}
