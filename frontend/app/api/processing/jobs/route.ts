import { forwardProtected } from "../../../../lib/server-api";
export async function POST(request: Request) { return forwardProtected("/processing/jobs", request); }
