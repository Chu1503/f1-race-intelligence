import { forwardProtected } from "../../../../lib/server-api";
export const maxDuration = 180;
export async function POST(request: Request) { return forwardProtected("/commentary", request); }
