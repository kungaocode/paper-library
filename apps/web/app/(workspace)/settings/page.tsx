"use client";

import {
  AlertCircle,
  CheckCircle2,
  Database,
  HardDrive,
  KeyRound,
  LoaderCircle,
  RefreshCw,
  ServerCog,
  TestTube2,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { fetchModelStatus, testModelConnection } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { ModelConnectionTest, ModelStatus } from "@/lib/types";

export default function SettingsPage() {
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionTest, setConnectionTest] =
    useState<ModelConnectionTest | null>(null);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError("");
    setConnectionTest(null);
    try {
      setModelStatus(await fetchModelStatus());
    } catch (reason) {
      setModelStatus(null);
      setError(
        reason instanceof Error
          ? reason.message
          : "无法读取模型状态，请确认 API 服务已启动。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const runConnectionTest = useCallback(async () => {
    setTestingConnection(true);
    setConnectionTest(null);
    try {
      setConnectionTest(await testModelConnection());
    } catch (reason) {
      setConnectionTest({
        ok: false,
        message:
          reason instanceof Error ? reason.message : "连接测试请求失败。",
        latencyMs: 0,
        provider: modelStatus?.provider ?? "",
        model: modelStatus?.model ?? "",
      });
    } finally {
      setTestingConnection(false);
    }
  }, [modelStatus]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const configured = modelStatus?.configured === true;

  return (
    <div>
      <PageHeader
        eyebrow="System"
        title="设置"
        description="模型配置只从后端环境变量读取，当前页面为只读状态。"
        actions={
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void loadStatus()}
            disabled={loading}
          >
            <RefreshCw className="h-4 w-4" />
            刷新状态
          </button>
        }
      />

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-5">
          <section className="panel">
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <div className="flex items-center gap-3">
                <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[#f0f2ef] text-muted">
                  <ServerCog className="h-4 w-4" />
                </span>
                <div>
                  <h2 className="text-sm font-semibold text-ink">模型接口</h2>
                  <p className="mt-1 text-[10px] text-muted">
                    由 apps/api/.env 决定，前端不可修改
                  </p>
                </div>
              </div>
              {loading ? (
                <span className="inline-flex h-7 items-center gap-1.5 rounded-full border border-line px-2.5 text-[10px] text-muted">
                  <LoaderCircle className="h-3 w-3 animate-spin" />
                  读取中
                </span>
              ) : (
                <span
                  className={cn(
                    "inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[10px] font-medium",
                    configured
                      ? "bg-accent-soft text-accent"
                      : "bg-signal-soft text-signal",
                  )}
                >
                  {configured ? (
                    <CheckCircle2 className="h-3 w-3" />
                  ) : (
                    <AlertCircle className="h-3 w-3" />
                  )}
                  {configured ? "已配置" : "未配置"}
                </span>
              )}
            </div>

            {error ? (
              <p className="m-5 border border-danger/25 bg-danger-soft px-3 py-2 text-xs leading-5 text-danger">
                {error}
              </p>
            ) : null}

            <div className="grid gap-5 p-5 sm:grid-cols-2">
              <label className="block">
                <span className="mb-2 block text-[11px] font-medium text-muted">
                  Provider
                </span>
                <input
                  className="field w-full disabled:cursor-not-allowed disabled:bg-[#f4f5f3] disabled:text-muted"
                  value={modelStatus?.provider ?? ""}
                  placeholder="未配置"
                  readOnly
                  disabled
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-[11px] font-medium text-muted">
                  模型
                </span>
                <input
                  className="field w-full disabled:cursor-not-allowed disabled:bg-[#f4f5f3] disabled:text-muted"
                  value={modelStatus?.model ?? ""}
                  placeholder="未配置"
                  readOnly
                  disabled
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-2 block text-[11px] font-medium text-muted">
                  Base URL
                </span>
                <input
                  className="field w-full font-mono text-xs disabled:cursor-not-allowed disabled:bg-[#f4f5f3] disabled:text-muted"
                  value={modelStatus?.baseUrl ?? ""}
                  placeholder="未配置"
                  readOnly
                  disabled
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-2 block text-[11px] font-medium text-muted">
                  API Key
                </span>
                <div className="relative">
                  <KeyRound className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
                  <input
                    className="field w-full px-9 disabled:cursor-not-allowed disabled:bg-[#f4f5f3] disabled:text-muted"
                    value=""
                    placeholder="密钥只保存在后端环境变量中，前端不回显"
                    readOnly
                    disabled
                  />
                </div>
              </label>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-4">
              <p className="text-[10px] text-muted">
                修改模型配置需要编辑后端环境变量并重启 API。
              </p>
              <button
                type="button"
                className="btn-secondary h-8 px-3 text-xs"
                onClick={() => void runConnectionTest()}
                disabled={!configured || loading || testingConnection}
                title="调用模型接口验证连接和鉴权"
              >
                {testingConnection ? (
                  <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <TestTube2 className="h-3.5 w-3.5" />
                )}
                {testingConnection ? "测试中" : "测试连接"}
              </button>
            </div>

            {connectionTest ? (
              <div
                className={cn(
                  "mx-5 mb-5 flex items-start gap-2 border px-3 py-2 text-xs leading-5",
                  connectionTest.ok
                    ? "border-accent/25 bg-accent-soft text-accent"
                    : "border-danger/25 bg-danger-soft text-danger",
                )}
                role="status"
                aria-live="polite"
              >
                {connectionTest.ok ? (
                  <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                ) : (
                  <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                )}
                <span>
                  {connectionTest.message}
                  {connectionTest.ok
                    ? ` 延迟 ${connectionTest.latencyMs} ms。`
                    : ""}
                </span>
              </div>
            ) : null}
          </section>

          <section className="panel">
            <div className="flex items-center gap-3 border-b border-line px-5 py-4">
              <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[#f0f2ef] text-muted">
                <HardDrive className="h-4 w-4" />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-ink">存储与处理</h2>
                <p className="mt-1 text-[10px] text-muted">
                  运行参数由后端环境变量决定，暂不支持在线修改
                </p>
              </div>
            </div>

            <div className="grid gap-5 p-5 sm:grid-cols-2">
              <label className="block sm:col-span-2">
                <span className="mb-2 block text-[11px] font-medium text-muted">
                  原始文件目录
                </span>
                <input
                  className="field w-full font-mono text-xs disabled:cursor-not-allowed disabled:bg-[#f4f5f3] disabled:text-muted"
                  value="./need_organization"
                  readOnly
                  disabled
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-[11px] font-medium text-muted">
                  最大下载大小
                </span>
                <input
                  className="field w-full disabled:cursor-not-allowed disabled:bg-[#f4f5f3] disabled:text-muted"
                  value="由后端 MAX_DOWNLOAD_MB 控制"
                  readOnly
                  disabled
                />
              </label>
              <label className="block">
                <span className="mb-2 block text-[11px] font-medium text-muted">
                  向量索引
                </span>
                <input
                  className="field w-full disabled:cursor-not-allowed disabled:bg-[#f4f5f3] disabled:text-muted"
                  value="尚未实现"
                  readOnly
                  disabled
                />
              </label>
            </div>
          </section>
        </div>

        <aside className="space-y-5">
          <section className="panel">
            <div className="border-b border-line px-5 py-4">
              <h2 className="text-sm font-semibold text-ink">真实服务状态</h2>
            </div>
            <div className="divide-y divide-line">
              <div className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-xs font-medium text-ink">模型接口</p>
                  <p className="mt-1 text-[10px] text-muted">
                    {modelStatus?.provider || "未知"} ·{" "}
                    {modelStatus?.model || "未指定模型"}
                  </p>
                </div>
                <span
                  className={cn(
                    "flex items-center gap-1.5 text-[10px] font-medium",
                    configured ? "text-accent" : "text-signal",
                  )}
                >
                  <span
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      configured ? "bg-accent" : "bg-signal",
                    )}
                  />
                  {configured ? "已配置" : "未配置"}
                </span>
              </div>
              <div className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-xs font-medium text-ink">存储后端</p>
                  <p className="mt-1 text-[10px] text-muted">
                    SQLite + 本地 PDF 目录
                  </p>
                </div>
                <span className="flex items-center gap-1.5 text-[10px] font-medium text-accent">
                  <span className="h-1.5 w-1.5 rounded-full bg-accent" />
                  正常
                </span>
              </div>
              <div className="flex items-center justify-between px-5 py-4">
                <div>
                  <p className="text-xs font-medium text-ink">向量索引</p>
                  <p className="mt-1 text-[10px] text-muted">
                    后端未实现，统计不可用
                  </p>
                </div>
                <span className="flex items-center gap-1.5 text-[10px] font-medium text-muted">
                  <span className="h-1.5 w-1.5 rounded-full bg-line" />
                  未接入
                </span>
              </div>
            </div>
          </section>

          <section className="panel bg-[#fafbf9] p-5">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-ink text-white">
              <Database className="h-5 w-5" />
            </span>
            <h2 className="mt-4 text-sm font-semibold text-ink">数据导出</h2>
            <p className="mt-2 text-[11px] leading-5 text-muted">
              KNOWLEDGE_BASE.md 由后端在导入归档时自动更新，暂未提供手动导出接口。
            </p>
            <button
              type="button"
              className="btn-secondary mt-5 w-full"
              disabled
              title="导出接口尚未接入"
            >
              导出 KNOWLEDGE_BASE.md
            </button>
          </section>

          <section className="panel p-5">
            <h2 className="text-sm font-semibold text-ink">提示词版本</h2>
            <p className="mt-2 text-[11px] leading-5 text-muted">
              当前提示词内置在 apps/api/app/pipeline.py，尚未提供版本元数据接口。
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
