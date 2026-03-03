package httpapi

import (
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/require"
)

func TestWriteError_WritesStructuredErrorResponse(t *testing.T) {
	rr := httptest.NewRecorder()

	WriteError(rr, http.StatusUnauthorized, "AUTH_INVALID_TOKEN", "invalid token")

	require.Equal(t, http.StatusUnauthorized, rr.Code)
	require.Equal(t, "application/json", rr.Header().Get("Content-Type"))
	require.JSONEq(t, `{"error_code":"AUTH_INVALID_TOKEN","message":"invalid token"}`, rr.Body.String())
}
