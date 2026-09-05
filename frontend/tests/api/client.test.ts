import { describe, expect, it, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../mocks/server";
import { API_BASE } from "../mocks/handlers";
import {
  ApiError,
  apiFetch,
  authHeader,
  clearCredentials,
  getStoredCredentials,
  login,
  storeCredentials,
} from "../../src/api/client";

beforeEach(() => {
  sessionStorage.clear();
  import.meta.env.VITE_API_BASE_URL = API_BASE;
});

describe("credential storage", () => {
  it("stores and retrieves credentials from sessionStorage", () => {
    expect(getStoredCredentials()).toBeNull();
    storeCredentials("admin", "secret");
    expect(getStoredCredentials()).toEqual({ username: "admin", password: "secret" });
    clearCredentials();
    expect(getStoredCredentials()).toBeNull();
  });

  it("builds a Basic auth header from stored credentials", () => {
    storeCredentials("admin", "secret");
    expect(authHeader()).toBe(`Basic ${btoa("admin:secret")}`);
  });

  it("throws if no credentials are stored", () => {
    expect(() => authHeader()).toThrow();
  });
});

describe("login", () => {
  it("stores credentials on success", async () => {
    await login("admin", "admin");
    expect(getStoredCredentials()).toEqual({ username: "admin", password: "admin" });
  });

  it("throws ApiError and does not store credentials on failure", async () => {
    await expect(login("admin", "wrong")).rejects.toBeInstanceOf(ApiError);
    expect(getStoredCredentials()).toBeNull();
  });
});

describe("apiFetch", () => {
  it("attaches the Basic auth header and parses JSON", async () => {
    server.use(
      http.get(`${API_BASE}/admin/docs`, ({ request }) => {
        if (request.headers.get("Authorization") !== `Basic ${btoa("admin:admin")}`) {
          return new HttpResponse(null, { status: 401 });
        }
        return HttpResponse.json([{ id: 1, filename: "a.txt" }]);
      })
    );
    storeCredentials("admin", "admin");
    const result = await apiFetch<{ id: number; filename: string }[]>("/admin/docs");
    expect(result).toEqual([{ id: 1, filename: "a.txt" }]);
  });

  it("clears credentials and throws ApiError on 401", async () => {
    server.use(http.get(`${API_BASE}/admin/docs`, () => new HttpResponse(null, { status: 401 })));
    storeCredentials("admin", "admin");
    await expect(apiFetch("/admin/docs")).rejects.toBeInstanceOf(ApiError);
    expect(getStoredCredentials()).toBeNull();
  });

  it("returns undefined for a 204 No Content response", async () => {
    server.use(http.delete(`${API_BASE}/admin/docs/1`, () => new HttpResponse(null, { status: 204 })));
    storeCredentials("admin", "admin");
    const result = await apiFetch("/admin/docs/1", { method: "DELETE" });
    expect(result).toBeUndefined();
  });
});
