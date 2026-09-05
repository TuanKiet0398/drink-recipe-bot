import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { WelcomePage } from "../../src/welcome/WelcomePage";

describe("WelcomePage", () => {
  it("renders the brand headline and a link into the admin login", () => {
    render(
      <MemoryRouter>
        <WelcomePage />
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: /steep the knowledge/i })).toBeInTheDocument();
    const cta = screen.getByRole("link", { name: "Enter Admin Panel" });
    expect(cta).toHaveAttribute("href", "/login");
  });

  it("lists the four admin panel features", () => {
    render(
      <MemoryRouter>
        <WelcomePage />
      </MemoryRouter>
    );

    expect(screen.getByText("Documents & Recipes")).toBeInTheDocument();
    expect(screen.getByText("Users")).toBeInTheDocument();
    expect(screen.getByText("Access Log")).toBeInTheDocument();
    expect(screen.getByText("Audit Log")).toBeInTheDocument();
  });
});
