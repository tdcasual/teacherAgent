package auth

import "context"

type StudentCredentialRepository interface {
	VerifyStudentCredential(ctx context.Context, studentID, credential string) (bool, error)
}
