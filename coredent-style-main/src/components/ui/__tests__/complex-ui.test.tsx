import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationPrevious,
  PaginationNext,
  PaginationEllipsis,
} from "../pagination";
import {
  NavigationMenu,
  NavigationMenuList,
  NavigationMenuItem,
  NavigationMenuTrigger,
  NavigationMenuContent,
  NavigationMenuLink,
} from "../navigation-menu";
import {
  Command,
  CommandDialog,
  CommandInput,
  CommandList,
  CommandEmpty,
  CommandGroup,
  CommandItem,
  CommandSeparator,
  CommandShortcut,
} from "../command";
import {
  Toast,
  ToastAction,
  ToastClose,
  ToastDescription,
  ToastProvider,
  ToastTitle,
  ToastViewport,
} from "../toast";
import { Toaster } from "../toaster";
import { toast as toastFn, useToast } from "@/hooks/use-toast";
import {
  Drawer,
  DrawerTrigger,
  DrawerContent,
  DrawerHeader,
  DrawerFooter,
  DrawerTitle,
  DrawerDescription,
  DrawerClose,
} from "../drawer";
import {
  InputOTP,
  InputOTPGroup,
  InputOTPSlot,
  InputOTPSeparator,
} from "../input-otp";
import { Toaster as SonnerToaster } from "../sonner";
import {
  Menubar,
  MenubarMenu,
  MenubarTrigger,
  MenubarContent,
  MenubarItem,
  MenubarSeparator,
  MenubarLabel,
  MenubarCheckboxItem,
  MenubarRadioGroup,
  MenubarRadioItem,
  MenubarSub,
  MenubarSubTrigger,
  MenubarSubContent,
  MenubarGroup,
} from "../menubar";

describe("ui: pagination", () => {
  it("renders a pagination nav with active and inactive links", () => {
    render(
      <Pagination>
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious href="#" />
          </PaginationItem>
          <PaginationItem>
            <PaginationLink href="#" isActive>
              1
            </PaginationLink>
          </PaginationItem>
          <PaginationItem>
            <PaginationLink href="#">2</PaginationLink>
          </PaginationItem>
          <PaginationItem>
            <PaginationEllipsis />
          </PaginationItem>
          <PaginationItem>
            <PaginationNext href="#" />
          </PaginationItem>
        </PaginationContent>
      </Pagination>,
    );
    expect(screen.getByRole("navigation", { name: /pagination/i })).toBeInTheDocument();
    expect(screen.getByText("1")).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("2")).not.toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Previous")).toBeInTheDocument();
    expect(screen.getByText("Next")).toBeInTheDocument();
    expect(screen.getByText("More pages")).toBeInTheDocument();
  });
});

describe("ui: navigation-menu", () => {
  it("renders a navigation menu with trigger and content", () => {
    render(
      <NavigationMenu>
        <NavigationMenuList>
          <NavigationMenuItem>
            <NavigationMenuTrigger>Open</NavigationMenuTrigger>
            <NavigationMenuContent>
              <NavigationMenuLink href="/x">Link</NavigationMenuLink>
            </NavigationMenuContent>
          </NavigationMenuItem>
        </NavigationMenuList>
      </NavigationMenu>,
    );
    expect(screen.getByText("Open")).toBeInTheDocument();
  });
});

describe("ui: command", () => {
  it("renders a command palette that filters items", async () => {
    const user = userEvent.setup();
    render(
      <Command>
        <CommandInput placeholder="Search..." />
        <CommandList>
          <CommandEmpty>No results.</CommandEmpty>
          <CommandGroup heading="Suggestions">
            <CommandItem>Apple</CommandItem>
            <CommandItem>Banana</CommandItem>
            <CommandSeparator />
            <CommandItem>
              Cherry
              <CommandShortcut>⌘C</CommandShortcut>
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>,
    );
    expect(screen.getByText("Apple")).toBeInTheDocument();
    expect(screen.getByText("⌘C")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Search..."), "ban");
    expect(screen.getByText("Banana")).toBeInTheDocument();
    expect(screen.queryByText("Apple")).toBeNull();
  });

  it("renders the command dialog with content", () => {
    render(
      <CommandDialog open>
        <CommandInput placeholder="Search..." />
        <CommandList>
          <CommandEmpty>No results.</CommandEmpty>
        </CommandList>
      </CommandDialog>,
    );
    expect(screen.getByPlaceholderText("Search...")).toBeInTheDocument();
  });
});

describe("ui: toast primitives", () => {
  it("renders a toast with title, description, action and close", async () => {
    const user = userEvent.setup();
    const onAction = vi.fn();
    render(
      <ToastProvider duration={1000}>
        <Toast open>
          <div>
            <ToastTitle>Title</ToastTitle>
            <ToastDescription>Description</ToastDescription>
          </div>
          <ToastAction altText="Undo" onClick={onAction}>
            Undo
          </ToastAction>
          <ToastClose />
        </Toast>
        <ToastViewport />
      </ToastProvider>,
    );
    expect(screen.getByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Description")).toBeInTheDocument();
    await user.click(screen.getByText("Undo"));
    expect(onAction).toHaveBeenCalled();
  });

  it("applies the destructive variant class", () => {
    const { container } = render(
      <ToastProvider>
        <Toast open variant="destructive">
          <ToastTitle>Err</ToastTitle>
        </Toast>
        <ToastViewport />
      </ToastProvider>,
    );
    expect(container.querySelector(".destructive")).toBeTruthy();
  });
});

describe("ui: toaster (use-toast)", () => {
  it("renders toasts dispatched via useToast", async () => {
    function Harness() {
      const { toast } = useToast();
      return (
        <>
          <button
            onClick={() =>
              toast({ title: "Hello", description: "World" })
            }
          >
            fire
          </button>
          <Toaster />
        </>
      );
    }
    const user = userEvent.setup();
    render(<Harness />);
    await user.click(screen.getByText("fire"));
    expect(await screen.findByText("Hello")).toBeInTheDocument();
    expect(screen.getByText("World")).toBeInTheDocument();
  });

  it("toast() returns handlers with dismiss and update", () => {
    const t = toastFn({ title: "x" });
    expect(typeof t.dismiss).toBe("function");
    expect(typeof t.update).toBe("function");
    expect(typeof t.id).toBe("string");
    t.dismiss();
  });
});

describe("ui: drawer", () => {
  it("renders a drawer with header, footer and content", async () => {
    const user = userEvent.setup();
    render(
      <Drawer>
        <DrawerTrigger asChild>
          <button>Open drawer</button>
        </DrawerTrigger>
        <DrawerContent>
          <DrawerHeader>
            <DrawerTitle>Title</DrawerTitle>
            <DrawerDescription>Desc</DrawerDescription>
          </DrawerHeader>
          <DrawerFooter>
            <button>Confirm</button>
            <DrawerClose asChild>
              <button>Cancel</button>
            </DrawerClose>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>,
    );
    await user.click(screen.getByText("Open drawer"));
    expect(await screen.findByText("Title")).toBeInTheDocument();
    expect(screen.getByText("Desc")).toBeInTheDocument();
  });
});

describe("ui: input-otp", () => {
  it("renders OTP slots and a separator", () => {
    render(
      <InputOTP maxLength={6}>
        <InputOTPGroup>
          <InputOTPSlot index={0} />
          <InputOTPSlot index={1} />
          <InputOTPSlot index={2} />
          <InputOTPSeparator />
          <InputOTPGroup>
            <InputOTPSlot index={3} />
          </InputOTPGroup>
        </InputOTPGroup>
      </InputOTP>,
    );
    // slots render empty divs; separator has role separator
    expect(screen.getByRole("separator")).toBeInTheDocument();
  });
});

describe("ui: sonner toaster", () => {
  it("renders without crashing and respects the theme", () => {
    const { container } = render(<SonnerToaster />);
    expect(container.firstChild).toBeTruthy();
  });
});

describe("ui: menubar", () => {
  it("renders a menubar with a menu, items, and a submenu", async () => {
    const user = userEvent.setup();
    render(
      <Menubar>
        <MenubarMenu>
          <MenubarTrigger>File</MenubarTrigger>
          <MenubarContent>
            <MenubarLabel>Actions</MenubarLabel>
            <MenubarItem>New</MenubarItem>
            <MenubarSeparator />
            <MenubarCheckboxItem checked>Auto-save</MenubarCheckboxItem>
            <MenubarSeparator />
            <MenubarSub>
              <MenubarSubTrigger>Export</MenubarSubTrigger>
              <MenubarSubContent>
                <MenubarItem>PDF</MenubarItem>
              </MenubarSubContent>
            </MenubarSub>
          </MenubarContent>
        </MenubarMenu>
        <MenubarMenu>
          <MenubarTrigger>Edit</MenubarTrigger>
          <MenubarContent>
            <MenubarGroup>
              <MenubarRadioGroup value="a">
                <MenubarRadioItem value="a">A</MenubarRadioItem>
              </MenubarRadioGroup>
            </MenubarGroup>
          </MenubarContent>
        </MenubarMenu>
      </Menubar>,
    );
    await user.click(screen.getByText("File"));
    expect(await screen.findByText("New")).toBeInTheDocument();
  });
});
