export const readFeatureFlag = (
  key: string,
  fallback: boolean,
  source: Record<string, string | undefined>,
): boolean => {
  const raw = source[key];
  if (raw == null) return fallback;
  const normalized = String(raw).trim().toLowerCase();
  return normalized === '1' || normalized === 'true';
};

export const readTeacherSurveyAnalysisFlag = (
  source: Record<string, string | undefined>,
): boolean => readFeatureFlag('teacherSurveyAnalysis', false, source)

export const readTeacherSurveyShadowFlag = (
  source: Record<string, string | undefined>,
): boolean => readFeatureFlag('teacherSurveyAnalysisShadow', true, source)
