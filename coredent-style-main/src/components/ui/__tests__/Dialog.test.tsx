import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogTrigger, DialogClose } from "../dialog";
import { Button } from "../button";

describe("Dialog", () => {
  it("renders dialog trigger button", () => {
    render(
      <Dialog>
        <DialogTrigger asChild>
          <Button>Open Dialog</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Test Dialog</DialogTitle>
          </DialogHeader>
          <p>Dialog content</p>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByRole("button", { name: /open dialog/i })).toBeInTheDocument();
  });

  it("renders dialog content when open", () => {
    render(
      <Dialog open={true}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Test Title</DialogTitle>
            <DialogDescription>Test description</DialogDescription>
          </DialogHeader>
          <p>Dialog body content</p>
          <DialogFooter>
            <Button>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByText("Test Title")).toBeInTheDocument();
    expect(screen.getByText("Test description")).toBeInTheDocument();
    expect(screen.getByText("Dialog body content")).toBeInTheDocument();
  });

  it("applies correct styles to DialogContent", () => {
    render(
      <Dialog open={true}>
        <DialogContent data-testid="dialog-content">
          <p>Content</p>
        </DialogContent>
      </Dialog>,
    );
    const content = screen.getByTestId("dialog-content");
    expect(content).toHaveClass("fixed");
    expect(content).toHaveClass("bg-background");
    expect(content).toHaveClass("p-6");
  });

  it("renders DialogClose button", () => {
    render(
      <Dialog open={true}>
        <DialogContent>
          <DialogClose data-testid="close-btn">Close</DialogClose>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByTestId("close-btn")).toBeInTheDocument();
  });

  it("renders DialogHeader", () => {
    render(
      <Dialog open={true}>
        <DialogContent>
          <DialogHeader>Header Content</DialogHeader>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByText("Header Content")).toBeInTheDocument();
  });

  it("renders DialogFooter", () => {
    render(
      <Dialog open={true}>
        <DialogContent>
          <DialogFooter>Footer Content</DialogFooter>
        </DialogContent>
      </Dialog>,
    );
    expect(screen.getByText("Footer Content")).toBeInTheDocument();
  });
});
