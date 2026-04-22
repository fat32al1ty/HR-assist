export type Resume = {
  id: number;
  original_filename: string;
  status: string;
  extracted_text: string | null;
  analysis: Record<string, unknown> | null;
  error_message: string | null;
  is_active: boolean;
  label: string | null;
  created_at: string;
};

export function resumeDisplayName(resume: Resume): string {
  return (resume.label && resume.label.trim()) || resume.original_filename;
}
