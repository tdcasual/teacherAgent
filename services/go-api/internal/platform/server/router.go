package server

import (
	"context"
	"fmt"
	"net/http"
	"os"

	adminapi "go-api/internal/api/admin"
	assignmentapi "go-api/internal/api/assignment"
	authapi "go-api/internal/api/auth"
	chatapi "go-api/internal/api/chat"
	chartsapi "go-api/internal/api/charts"
	examapi "go-api/internal/api/exam"
	filesapi "go-api/internal/api/files"
	jobsapi "go-api/internal/api/jobs"
	appadmin "go-api/internal/app/admin"
	appassignment "go-api/internal/app/assignment"
	appauth "go-api/internal/app/auth"
	appchat "go-api/internal/app/chat"
	appexam "go-api/internal/app/exam"
	appfiles "go-api/internal/app/files"
	domainchat "go-api/internal/domain/chat"
	dbinfra "go-api/internal/infra/db"
	storageinfra "go-api/internal/infra/storage"
	httpapi "go-api/internal/platform/http"

	"github.com/go-chi/chi/v5"
)

type studentTokenIssuer struct{}

func (studentTokenIssuer) IssueStudentToken(_ context.Context, studentID string) (string, error) {
	return fmt.Sprintf("token-%s", studentID), nil
}

type teacherTokenGenerator struct{}

func (teacherTokenGenerator) NewToken() string {
	return "T-NEW-1"
}

type staticJobStateResolver struct{}

func (staticJobStateResolver) ResolveJobState(_ context.Context, _ string) (string, error) {
	return "done", nil
}

type authLoginAdapter struct {
	uc appauth.Usecase
}

func (a authLoginAdapter) StudentLogin(ctx context.Context, in authapi.StudentLoginInput) (authapi.StudentLoginOutput, error) {
	out, err := a.uc.StudentLogin(ctx, appauth.StudentLoginInput{
		StudentID:  in.StudentID,
		Credential: in.Credential,
	})
	if err != nil {
		return authapi.StudentLoginOutput{}, err
	}
	return authapi.StudentLoginOutput{AccessToken: out.AccessToken}, nil
}

type filesUploadAdapter struct {
	uc appfiles.Usecase
}

func (a filesUploadAdapter) Upload(ctx context.Context, in filesapi.UploadInput) (filesapi.UploadOutput, error) {
	out, err := a.uc.Upload(ctx, appfiles.UploadInput{
		FileName:  in.FileName,
		SizeBytes: in.SizeBytes,
	})
	if err != nil {
		return filesapi.UploadOutput{}, err
	}
	return filesapi.UploadOutput{ResourceID: out.ResourceID}, nil
}

type assignmentConfirmAdapter struct {
	uc appassignment.Usecase
}

func (a assignmentConfirmAdapter) ConfirmDraft(ctx context.Context, in assignmentapi.ConfirmDraftInput) (assignmentapi.ConfirmDraftOutput, error) {
	out, err := a.uc.ConfirmDraft(ctx, appassignment.ConfirmDraftInput{
		DraftID: in.DraftID,
	})
	if err != nil {
		return assignmentapi.ConfirmDraftOutput{}, err
	}
	return assignmentapi.ConfirmDraftOutput{Status: out.Status}, nil
}

type examParseAdapter struct {
	uc appexam.Usecase
}

func (a examParseAdapter) CreateExamParseJob(ctx context.Context, in examapi.CreateExamParseJobInput) (examapi.CreateExamParseJobOutput, error) {
	out, err := a.uc.CreateExamParseJob(ctx, appexam.CreateExamParseJobInput{
		ResourceID: in.ResourceID,
	})
	if err != nil {
		return examapi.CreateExamParseJobOutput{}, err
	}
	return examapi.CreateExamParseJobOutput{JobID: out.JobID}, nil
}

type chatAdapter struct {
	uc appchat.Usecase
}

func (a chatAdapter) SendMessage(ctx context.Context, in chatapi.SendMessageInput) (chatapi.SendMessageOutput, error) {
	out, err := a.uc.SendMessage(ctx, appchat.SendMessageInput{
		SessionID: in.SessionID,
		Message:   in.Message,
	})
	if err != nil {
		return chatapi.SendMessageOutput{}, err
	}
	return chatapi.SendMessageOutput{JobID: out.JobID}, nil
}

func (a chatAdapter) StreamJobEvents(ctx context.Context, jobID string) (<-chan domainchat.JobEvent, error) {
	return a.uc.StreamJobEvents(ctx, jobID)
}

type adminResetTokenAdapter struct {
	uc appadmin.Usecase
}

func (a adminResetTokenAdapter) ResetTeacherToken(ctx context.Context, in adminapi.ResetTeacherTokenInput) (adminapi.ResetTeacherTokenOutput, error) {
	out, err := a.uc.ResetTeacherToken(ctx, appadmin.ResetTeacherTokenInput{
		TeacherID: in.TeacherID,
	})
	if err != nil {
		return adminapi.ResetTeacherTokenOutput{}, err
	}
	return adminapi.ResetTeacherTokenOutput{Token: out.Token}, nil
}

func NewRouter() http.Handler {
	authRepo := dbinfra.NewAuthRepoPG()
	authUC := appauth.NewUsecase(authRepo, studentTokenIssuer{})
	authHandler := authapi.NewHandler(authLoginAdapter{uc: authUC})

	filesStore := storageinfra.NewLocalStorage()
	filesUC := appfiles.NewUsecase(filesStore, 50<<20)
	filesHandler := filesapi.NewHandler(filesUploadAdapter{uc: filesUC})

	assignmentRepo := dbinfra.NewAssignmentRepoPG()
	assignmentUC := appassignment.NewUsecase(assignmentRepo)
	assignmentHandler := assignmentapi.NewHandler(assignmentConfirmAdapter{uc: assignmentUC})

	examQueue := dbinfra.NewExamQueuePG()
	examUC := appexam.NewUsecase(examQueue)
	examHandler := examapi.NewHandler(examParseAdapter{uc: examUC})

	chatRepo := dbinfra.NewChatRepoPG()
	chatUC := appchat.NewUsecase(chatRepo, chatRepo)
	chatUCA := chatAdapter{uc: chatUC}
	chatHandler := chatapi.NewHandler(chatUCA)
	chatSSEHandler := chatapi.NewSSEHandler(chatUCA)

	adminRepo := dbinfra.NewAdminRepoPG()
	adminUC := appadmin.NewUsecase(adminRepo, teacherTokenGenerator{})
	adminHandler := adminapi.NewHandler(adminResetTokenAdapter{uc: adminUC})

	jobsHandler := jobsapi.NewHandler(staticJobStateResolver{})
	chartsHandler := chartsapi.NewHandler(os.Getenv("GO_API_UPLOADS_DIR"))

	r := chi.NewRouter()
	r.Get("/healthz", httpapi.HealthHandler)
	r.Get("/health", httpapi.HealthHandler)
	r.Get("/charts/{runID}/{fileName}", chartsHandler.ChartImageFile)
	r.Get("/chart-runs/{runID}/meta", chartsHandler.ChartRunMeta)

	r.Route("/api/v2", func(v2 chi.Router) {
		v2.Post("/auth/student/login", authHandler.StudentLogin)
		v2.Post("/files/upload", filesHandler.Upload)
		v2.Post("/assignment/confirm", assignmentHandler.ConfirmDraft)
		v2.Post("/exam/parse", examHandler.CreateExamParseJob)
		v2.Post("/chat/send", chatHandler.SendMessage)
		v2.Get("/chat/events", chatSSEHandler.StreamJobEvents)
		v2.Get("/jobs/{jobID}", jobsHandler.GetStatus)
		v2.Post("/admin/teacher/reset-token", adminHandler.ResetTeacherToken)
	})

	return r
}
