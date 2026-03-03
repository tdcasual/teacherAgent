package exam

import "errors"

type JobType string

const JobTypeExamParse JobType = "exam.parse"

var ErrExamResourceRequired = errors.New("exam resource is required")
