import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption } from "../table";

describe("Table", () => {
  it("renders Table element", () => {
    render(<Table data-testid="table"><tbody><tr><td>Cell</td></tr></tbody></Table>);
    expect(screen.getByTestId("table")).toBeInTheDocument();
  });

  it("applies base Table styles", () => {
    render(<Table data-testid="table"><tbody><tr><td>Cell</td></tr></tbody></Table>);
    const table = screen.getByTestId("table");
    expect(table).toHaveClass("w-full");
    expect(table).toHaveClass("caption-bottom");
    expect(table).toHaveClass("text-sm");
  });

  it("renders TableHeader", () => {
    render(<Table><TableHeader data-testid="header"><tr><th>Header</th></tr></TableHeader></Table>);
    expect(screen.getByTestId("header")).toBeInTheDocument();
  });

  it("renders TableBody", () => {
    render(<Table><TableBody data-testid="body"><tr><td>Body</td></tr></TableBody></Table>);
    expect(screen.getByTestId("body")).toBeInTheDocument();
  });

  it("renders TableFooter", () => {
    render(<Table><TableFooter data-testid="footer"><tr><td>Footer</td></tr></TableFooter></Table>);
    expect(screen.getByTestId("footer")).toBeInTheDocument();
  });

  it("renders TableHead", () => {
    render(<Table><TableHeader><tr><TableHead data-testid="head">Head</TableHead></tr></TableHeader></Table>);
    expect(screen.getByTestId("head")).toBeInTheDocument();
  });

  it("renders TableRow", () => {
    render(<Table><TableBody><TableRow data-testid="row"><td>Row</td></TableRow></TableBody></Table>);
    const row = screen.getByTestId("row");
    expect(row).toHaveClass("border-b");
  });

  it("renders TableCell", () => {
    render(<Table><TableBody><tr><TableCell data-testid="cell">Cell</TableCell></tr></TableBody></Table>);
    expect(screen.getByTestId("cell")).toBeInTheDocument();
  });

  it("renders TableCaption", () => {
    render(<Table><TableCaption data-testid="caption">Caption</TableCaption><tbody><tr><td>Cell</td></tr></tbody></Table>);
    expect(screen.getByTestId("caption")).toBeInTheDocument();
  });

  it("renders full table composition", () => {
    render(
      <Table>
        <TableCaption>Patients List</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Email</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>John Doe</TableCell>
            <TableCell>john@example.com</TableCell>
          </TableRow>
        </TableBody>
        <TableFooter>
          <TableRow>
            <TableCell colSpan={2}>Total: 1</TableCell>
          </TableRow>
        </TableFooter>
      </Table>,
    );
    expect(screen.getByText("Patients List")).toBeInTheDocument();
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("John Doe")).toBeInTheDocument();
    expect(screen.getByText("john@example.com")).toBeInTheDocument();
    expect(screen.getByText("Total: 1")).toBeInTheDocument();
  });
});
