import { forwardProtected } from "../../../../../lib/server-api";
export async function GET(_request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return forwardProtected(`/processing/jobs/${encodeURIComponent(jobId)}`);
}
