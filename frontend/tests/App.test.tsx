import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../src/App";

describe("App", () => {
  it("renders the admin app root", () => {
    render(<App />);
    expect(screen.getByText("Matcha Bot Admin")).toBeInTheDocument();
  });
});
