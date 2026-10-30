import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  AlertDialog,
  AlertDialogTrigger,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from "../alert-dialog";

describe("AlertDialog", () => {
  it("renders AlertDialogTrigger with children", () => {
    render(
      <AlertDialog>
        <AlertDialogTrigger>Open Alert</AlertDialogTrigger>
      </AlertDialog>,
    );
    expect(screen.getByText("Open Alert")).toBeInTheDocument();
  });

  it("renders AlertDialogHeader", () => {
    const { container } = render(<AlertDialogHeader>Header content</AlertDialogHeader>);
    const header = container.firstChild as HTMLElement;
    expect(header).toBeInTheDocument();
    expect(header).toHaveClass("flex");
    expect(header).toHaveClass("flex-col");
    expect(header).toHaveClass("space-y-2");
  });

  it("renders AlertDialogFooter", () => {
    const { container } = render(<AlertDialogFooter>Footer content</AlertDialogFooter>);
    const footer = container.firstChild as HTMLElement;
    expect(footer).toBeInTheDocument();
    expect(footer).toHaveClass("flex");
    expect(footer).toHaveClass("flex-col-reverse");
  });

  it("renders AlertDialogTitle", () => {
    render(
      <AlertDialog defaultOpen>
        <AlertDialogTrigger>Open</AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogTitle>Alert Title</AlertDialogTitle>
        </AlertDialogContent>
      </AlertDialog>
    );
    const title = screen.getByText("Alert Title");
    expect(title).toBeInTheDocument();
  });

  it("renders AlertDialogDescription", () => {
    render(
      <AlertDialog defaultOpen>
        <AlertDialogTrigger>Open</AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogDescription>Description text</AlertDialogDescription>
        </AlertDialogContent>
      </AlertDialog>
    );
    const desc = screen.getByText("Description text");
    expect(desc).toBeInTheDocument();
  });

  it("renders complete alert dialog trigger", () => {
    render(
      <AlertDialog>
        <AlertDialogTrigger>Delete</AlertDialogTrigger>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
            <AlertDialogDescription>This action cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>,
    );
    expect(screen.getByText("Delete")).toBeInTheDocument();
  });

  it("renders AlertDialogContent when open", () => {
    render(
      <AlertDialog defaultOpen>
        <AlertDialogTrigger>Open</AlertDialogTrigger>
        <AlertDialogContent>Alert content</AlertDialogContent>
      </AlertDialog>,
    );
    const content = screen.getByText("Alert content");
    expect(content).toBeInTheDocument();
  });
});
