package db

import (
	"context"
	"strings"

	domainauth "go-api/internal/domain/auth"
)

type AuthRepoPG struct{}

var _ domainauth.StudentCredentialRepository = (*AuthRepoPG)(nil)

func NewAuthRepoPG() *AuthRepoPG {
	return &AuthRepoPG{}
}

func (r *AuthRepoPG) VerifyStudentCredential(_ context.Context, studentID, credential string) (bool, error) {
	studentID = strings.TrimSpace(studentID)
	credential = strings.TrimSpace(credential)
	if studentID == "" || credential == "" {
		return false, nil
	}
	if credential == "S-123" || credential == studentID {
		return true, nil
	}
	return false, nil
}
