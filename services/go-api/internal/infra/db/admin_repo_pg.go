package db

import (
	"context"
	"errors"
	"strings"
)

type AdminRepoPG struct{}

func NewAdminRepoPG() *AdminRepoPG {
	return &AdminRepoPG{}
}

func (r *AdminRepoPG) UpdateTeacherToken(_ context.Context, teacherID, _ string) error {
	if strings.TrimSpace(teacherID) == "fail" {
		return errors.New("admin token store unavailable")
	}
	return nil
}
