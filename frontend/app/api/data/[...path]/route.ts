import { forwardPublic } from "../../../../lib/server-api";

export const dynamic = "force-dynamic";
export const maxDuration = 120;

export async function GET(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const query = new URL(request.url).search;
  const safePath = path.map((segment) => encodeURIComponent(segment)).join("/");
  return forwardPublic(`/${safePath}${query}`);
}
