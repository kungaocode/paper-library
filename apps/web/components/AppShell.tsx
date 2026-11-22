"use client";

import {
  BookOpenText,
  Bot,
  ChevronDown,
  CircleUserRound,
  FolderTree,
  Inbox,
  LayoutDashboard,
  Menu,
  Search,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  useEffect,
  useRef,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";

import { apiFetch, fetchModelStatus } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { ModelStatus } from "@/lib/types";

const navigation = [
  { href: "/", label: "总览", icon: LayoutDashboard },
  { href: "/papers", label: "论文库", icon: BookOpenText },
  { href: "/inbox", label: "上传与处理", icon: Inbox },
  { href: "/categories", label: "分类管理", icon: FolderTree },
  { href: "/assistant", label: "AI 解读", icon: Bot },
  { href: "/review", label: "复核队列", icon: ShieldCheck },
];

function NavLink({
  href,
  label,
  icon: Icon,
  onNavigate,
  compact = false,
}: {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  onNavigate?: () => void;
  compact?: boolean;
}) {
  const pathname = usePathname();
  const active =
    href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);

  return (
    <Link
      href={href}
      onClick={onNavigate}
      aria-label={compact ? label : undefined}
      title={compact ? label : undefined}
      className={cn(
        "group flex h-10 items-center rounded-md text-sm transition-colors",
        compact ? "justify-center px-0" : "gap-3 px-3",
        active
          ? "bg-white/10 text-white"
          : "text-white/62 hover:bg-white/[0.06] hover:text-white",
      )}
    >
      <Icon
        className={cn(
          "h-[18px] w-[18px]",
          active ? "text-[#7dd3c7]" : "text-white/48 group-hover:text-white/80",
        )}
      />
      {!compact ? <span>{label}</span> : null}
      {active && !compact ? (
        <span className="ml-auto h-1.5 w-1.5 rounded-full bg-[#7dd3c7]" />
      ) : null}
    </Link>
  );
}

function SidebarContent({
  onNavigate,
  compact = false,
}: {
  onNavigate?: () => void;
  compact?: boolean;
}) {
  return (
    <div className="flex h-full flex-col">
      <div
        className={cn(
          "flex h-20 items-center border-b border-white/10",
          compact ? "justify-center px-0" : "px-5",
        )}
      >
        <Link
          href="/"
          className={cn("flex items-center", compact ? "justify-center" : "gap-3")}
          onClick={onNavigate}
          aria-label={compact ? "Paper Atlas" : undefined}
          title={compact ? "Paper Atlas" : undefined}
        >
          <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[#d8f0eb] text-ink">
            <BookOpenText className="h-5 w-5" />
          </span>
          {!compact ? (
            <span>
              <strong className="block text-sm font-semibold tracking-[0.01em] text-white">
                Paper Atlas
              </strong>
              <span className="block text-[10px] uppercase tracking-[0.13em] text-white/45">
                Research Library
              </span>
            </span>
          ) : null}
        </Link>
      </div>

      <nav
        className={cn(
          "flex-1 space-y-1 py-5",
          compact ? "px-2" : "px-3",
        )}
      >
        {!compact ? (
          <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.15em] text-white/35">
            Workspace
          </p>
        ) : null}
        {navigation.map((item) => (
          <NavLink
            key={item.href}
            {...item}
            onNavigate={onNavigate}
            compact={compact}
          />
        ))}
      </nav>

      <div className={cn("border-t border-white/10", compact ? "p-2" : "p-3")}>
        <NavLink
          href="/settings"
          label="设置"
          icon={Settings}
          onNavigate={onNavigate}
          compact={compact}
        />
        {!compact ? (
          <div className="mt-3 flex items-center gap-3 rounded-md bg-white/[0.055] px-3 py-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10">
              <CircleUserRound className="h-4 w-4 text-white/75" />
            </span>
            <span className="min-w-0 flex-1">
              <strong className="block truncate text-xs font-medium text-white">
                Local researcher
              </strong>
              <span className="flex items-center gap-1.5 text-[10px] text-white/45">
                <span className="h-1.5 w-1.5 rounded-full bg-[#56b8a9]" />
                Private workspace
              </span>
            </span>
            <ChevronDown className="h-3.5 w-3.5 text-white/35" />
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [modelStatusError, setModelStatusError] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const router = useRouter();

  useEffect(() => {
    let active = true;
    fetchModelStatus()
      .then((status) => {
        if (!active) return;
        setModelStatus(status);
        setModelStatusError("");
      })
      .catch((error) => {
        if (!active) return;
        setModelStatus(null);
        setModelStatusError(
          error instanceof Error ? error.message : "服务状态不可用",
        );
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    function focusSearch(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isEditing =
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT" ||
        target?.isContentEditable;
      if (event.key === "/" && !isEditing) {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }

    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = searchQuery.trim();
    router.push(query ? `/papers?q=${encodeURIComponent(query)}` : "/papers");
  }

  async function logout() {
    try {
      await apiFetch<void>("/api/auth/logout", { method: "POST" });
    } catch {
      // The backend cookie is HttpOnly; the redirect still protects the UI shell.
    }
    document.cookie = "paper_session=; Max-Age=0; path=/";
    router.push("/login");
    router.refresh();
  }

  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-16 bg-ink lg:block">
        <SidebarContent compact />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="关闭导航"
            className="absolute inset-0 bg-ink/50"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="relative h-full w-[290px] bg-ink shadow-xl">
            <button
              type="button"
              aria-label="关闭导航"
              className="absolute right-3 top-3 z-10 flex h-9 w-9 items-center justify-center rounded-md text-white/60 hover:bg-white/10 hover:text-white"
              onClick={() => setMobileOpen(false)}
            >
              <X className="h-4 w-4" />
            </button>
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="lg:pl-16">
        <header className="sticky top-0 z-20 flex h-14 items-center border-b border-line bg-canvas/95 px-3 backdrop-blur sm:px-4">
          <button
            type="button"
            className="icon-btn mr-3 lg:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="打开导航"
          >
            <Menu className="h-4 w-4" />
          </button>

          <form
            className="relative hidden w-full max-w-sm sm:block"
            onSubmit={submitSearch}
          >
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              ref={searchRef}
              className="field w-full pl-9"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="搜索标题、作者或内容"
              aria-label="全局搜索"
            />
            <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-line bg-[#f7f8f6] px-1.5 py-0.5 text-[10px] text-muted">
              /
            </span>
          </form>

          <div className="ml-auto flex items-center gap-3">
            <span className="hidden items-center gap-2 text-xs text-muted md:flex">
              <span
                className={cn(
                  "h-1.5 w-1.5 rounded-full",
                  modelStatus?.configured && !modelStatusError
                    ? "bg-accent"
                    : modelStatusError || modelStatus
                      ? "bg-signal"
                      : "bg-line",
                )}
              />
              {modelStatusError
                ? "服务状态不可用"
                : modelStatus
                  ? modelStatus.configured
                    ? `${modelStatus.provider} · 模型已配置`
                    : "模型未配置"
                  : "正在检查服务"}
            </span>
            <button
              type="button"
              onClick={logout}
              className="text-xs font-medium text-muted transition-colors hover:text-ink"
            >
              退出
            </button>
          </div>
        </header>

        <main className="mx-auto min-h-[calc(100vh-3.5rem)] max-w-[1920px] px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
