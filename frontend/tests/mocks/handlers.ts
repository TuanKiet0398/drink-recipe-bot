import { http, HttpResponse } from "msw";

export const API_BASE = "http://localhost:3000";

export const handlers = [
  http.post(`${API_BASE}/admin/login`, ({ request }) => {
    const auth = request.headers.get("Authorization");
    if (auth === `Basic ${btoa("admin:admin")}`) {
      return HttpResponse.json({ status: "ok" });
    }
    return new HttpResponse(null, { status: 401 });
  }),
];
