"use client";

import { ArrowRight, BookOpenText, LockKeyhole, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { apiFetch } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });

      router.push("/");
      router.refresh();
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "登录失败";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="grid min-h-screen bg-[#ecefeb] lg:grid-cols-[minmax(0,1.15fr)_minmax(420px,0.85fr)]">
      <section className="relative hidden overflow-hidden bg-ink px-12 py-10 text-white lg:flex lg:flex-col">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-md bg-[#d8f0eb] text-ink">
            <BookOpenText className="h-5 w-5" />
          </span>
          <span>
            <strong className="block text-base font-semibold">Paper Atlas</strong>
            <span className="block text-[10px] uppercase tracking-[0.16em] text-white/40">
              Research Library
            </span>
          </span>
        </div>

        <div className="my-auto max-w-[720px]">
          <div className="mb-8 flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-[#7dd3c7]">
            <span className="h-px w-10 bg-[#7dd3c7]" />
            Personal research workspace
          </div>
          <h1 className="max-w-[640px] text-[46px] font-semibold leading-[1.12] tracking-[-0.035em]">
            把论文从文件目录，
            <br />
            整理成可检索的知识体系。
          </h1>
          <p className="mt-6 max-w-[560px] text-base leading-7 text-white/55">
            阅读、分类、解读、问答与人工复核集中在同一条研究流程中。
          </p>

          <div className="relative mt-14 h-[260px] max-w-[620px]">
            <div className="absolute left-0 top-4 h-[230px] w-[390px] rotate-[-4deg] border border-white/10 bg-white/[0.055] p-6">
              <div className="mb-6 flex items-center justify-between">
                <span className="h-2 w-24 rounded bg-white/20" />
                <span className="text-[10px] uppercase tracking-[0.14em] text-white/25">
                  Page 04
                </span>
              </div>
              <div className="space-y-3">
                <span className="block h-2 w-[88%] rounded bg-white/15" />
                <span className="block h-2 w-[76%] rounded bg-white/12" />
                <span className="block h-2 w-[92%] rounded bg-white/10" />
                <span className="block h-2 w-[62%] rounded bg-white/10" />
              </div>
              <div className="mt-8 grid grid-cols-2 gap-4">
                <div className="h-20 border border-[#7dd3c7]/30 bg-[#7dd3c7]/10" />
                <div className="space-y-3">
                  <span className="block h-2 w-full rounded bg-white/12" />
                  <span className="block h-2 w-[78%] rounded bg-white/10" />
                  <span className="block h-2 w-[86%] rounded bg-white/10" />
                </div>
              </div>
            </div>
            <div className="absolute bottom-0 right-0 h-[220px] w-[320px] rotate-[3deg] border border-white/10 bg-[#243033] p-6 shadow-2xl">
              <div className="flex items-center gap-3">
                <span className="flex h-8 w-8 items-center justify-center rounded bg-[#d8f0eb] text-ink">
                  <ShieldCheck className="h-4 w-4" />
                </span>
                <span className="text-xs font-medium text-white/80">
                  AI Analysis
                </span>
              </div>
              <div className="mt-6 space-y-4">
                <div>
                  <span className="text-[10px] uppercase tracking-[0.13em] text-white/30">
                    Confidence
                  </span>
                  <div className="mt-2 h-1.5 rounded bg-white/10">
                    <div className="h-1.5 w-[92%] rounded bg-[#7dd3c7]" />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  {[1, 2, 3, 4, 5, 6].map((item) => (
                    <span
                      key={item}
                      className="h-8 border border-white/10 bg-white/[0.045]"
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-white/10 pt-5 text-[11px] text-white/35">
          <span>Local-first paper library</span>
          <span>67 papers · 12 categories</span>
        </div>
      </section>

      <section className="flex items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-[420px]">
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-ink text-white">
              <BookOpenText className="h-5 w-5" />
            </span>
            <strong>Paper Atlas</strong>
          </div>

          <p className="page-kicker mb-3">Private workspace</p>
          <h2 className="text-3xl font-semibold tracking-[-0.025em] text-ink">
            登录知识库
          </h2>
          <p className="mt-3 text-sm leading-6 text-muted">
            使用个人账号进入论文阅读与整理工作区。
          </p>

          <form className="mt-9 space-y-5" onSubmit={submit}>
            <label className="block">
              <span className="mb-2 block text-xs font-medium text-ink">
                用户名
              </span>
              <input
                className="field w-full"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                autoComplete="username"
                required
              />
            </label>

            <label className="block">
              <span className="mb-2 block text-xs font-medium text-ink">
                密码
              </span>
              <div className="relative">
                <LockKeyhole className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                <input
                  className="field w-full pl-9"
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="输入访问密码"
                  autoComplete="current-password"
                  required
                />
              </div>
            </label>

            {error ? (
              <p className="border-l-2 border-danger bg-danger-soft px-3 py-2 text-xs text-danger">
                {error}
              </p>
            ) : null}

            <button
              className="btn-primary h-11 w-full"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "正在验证" : "进入工作区"}
              <ArrowRight className="h-4 w-4" />
            </button>
          </form>

          <p className="mt-8 text-center text-[11px] leading-5 text-muted">
            登录凭证由内网后端的环境变量控制。
          </p>
        </div>
      </section>
    </main>
  );
}
