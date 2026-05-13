"use client"

import React, { useEffect, useState, useCallback, useRef, useLayoutEffect } from "react"
import Link from "next/link"
import Image from "next/image"
import { usePathname, useSearchParams } from "next/navigation"
import gsmsvLogo from "@/public/gsmsv_logo.jpg"
import { cn } from "@/lib/utils"
import {
  Server,
  LayoutDashboard,
  Rocket,
  Book,
  Settings,
  HelpCircle,
  Monitor,
  Loader2,
  Zap,
  HardDrive,
  Terminal,
  KeyRound,
  Cpu,
  FolderKanban,
  MessageCircleQuestion,
  MessageSquarePlus,
  ChevronDown,
  UserCheck,
  X,
} from "lucide-react"
import { getMyVms, getAllVms, type VmInfo, type AdminNodeVms } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet"

type NavItemData = {
  title: string
  label?: React.ReactNode
  href: string
  icon: React.ComponentType<{ className?: string }>
  external?: boolean
}

const mainNavItems: NavItemData[] = [
  { title: "인스턴스", href: "/instances", icon: Server },
  { title: "VM 생성", href: "/deploy", icon: Rocket },
  { title: "서버리스", href: "/serverless", icon: Zap },
]

// 문서 카테고리 (하위 카테고리 지원)
type DocCategory = NavItemData & { children?: NavItemData[] }

const docCategories: DocCategory[] = [
  {
    title: "시작하기", href: "/docs/getting-started", icon: Zap,
    children: [
      { title: "인스턴스", href: "/docs/instances", icon: HardDrive },
      { title: "접속 방법", href: "/docs/access", icon: Terminal },
      { title: "SSH Key 등록", label: <>SSH Key<br />등록</>, href: "/docs/ssh-key", icon: KeyRound },
      { title: "Public IP / GPU 안내", href: "/docs/advanced-resources", icon: Cpu },
    ],
  },
  { title: "FAQ", href: "/docs/faq", icon: MessageCircleQuestion },
  { title: "질문 등록", href: "/docs/questions", icon: MessageSquarePlus },
]

const footerNavItems: NavItemData[] = [
  { title: "설정", href: "/settings", icon: Settings },
  { title: "지원", href: process.env.NEXT_PUBLIC_DISCORD_URL || "#", icon: HelpCircle, external: true },
]

// ── 슬라이딩 인디케이터 ─────────────────────────────────────

interface IndicatorStyle {
  top: number
  height: number
  visible: boolean
}

function SlidingIndicator({ style }: { style: IndicatorStyle }) {
  if (!style.visible) return null

  return (
    <div
      className="absolute right-0 pointer-events-none"
      style={{
        top: style.top,
        height: style.height,
        transition: "top 0.15s cubic-bezier(0.4, 0, 0.2, 1), height 0.15s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.15s ease",
        opacity: style.visible ? 1 : 0,
        width: "calc(100% - 8px)",
        marginLeft: "8px",
      }}
    >
      <div className="absolute inset-0 bg-background rounded-l-xl" />
      <div className="absolute left-0 top-2 bottom-2 w-1 rounded-full bg-gray-500 dark:bg-gray-400 z-10" />
      <div
        className="absolute -top-4 right-0 h-4 w-4 bg-background"
        style={{ clipPath: "polygon(100% 0, 100% 100%, 0 100%)" }}
      >
        <div className="absolute inset-0 bg-sidebar" style={{ borderBottomRightRadius: "16px" }} />
      </div>
      <div
        className="absolute -bottom-4 right-0 h-4 w-4 bg-background"
        style={{ clipPath: "polygon(100% 0, 100% 100%, 0 0)" }}
      >
        <div className="absolute inset-0 bg-sidebar" style={{ borderTopRightRadius: "16px" }} />
      </div>
    </div>
  )
}

// ── NavItem (인디케이터 연동) ────────────────────────────────

interface NavItemProps {
  item: NavItemData
  isActive: boolean
  itemRef: React.RefCallback<HTMLDivElement>
}

function NavItem({ item, isActive, itemRef }: NavItemProps) {
  const Icon = item.icon
  return (
    <div ref={itemRef} className="relative">
      <Link
        href={item.href}
        className={cn(
          "relative flex items-center gap-2.5 px-3 py-2.5 text-[13px] font-medium transition-all duration-200 z-[1]",
          isActive
            ? "text-foreground rounded-l-xl ml-2"
            : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 rounded-lg mx-2"
        )}
      >
        <Icon className={cn("h-4.5 w-4.5 transition-colors", isActive ? "text-foreground" : "")} />
        <span>{item.title}</span>
      </Link>
    </div>
  )
}

// ── VM 상태 점 ───────────────────────────────────────────────

function VmStatusDot({ status }: { status: string }) {
  const color =
    status === "running"
      ? "bg-[var(--status-active-dot)]"
      : status === "stopped"
        ? "bg-[var(--status-stopped-dot)]"
        : "bg-[var(--status-pending-dot)]"

  return (
    <span
      className={cn(
        "h-1.5 w-1.5 rounded-full shrink-0",
        color,
        status === "running" && "animate-pulse"
      )}
    />
  )
}

// ── Sidebar 본체 ─────────────────────────────────────────────

export function Sidebar({
  mobileOpen = false,
  onMobileClose,
}: {
  mobileOpen?: boolean
  onMobileClose?: () => void
}) {
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const currentNode = searchParams.get("node")
  const { user } = useAuth()
  const isAdmin = user?.role === "admin"

  const [vms, setVms] = useState<VmInfo[]>([])
  const [adminNodes, setAdminNodes] = useState<AdminNodeVms[]>([])
  const [vmLoading, setVmLoading] = useState(true)
  const [docsOpen, setDocsOpen] = useState(false)
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set())

  const itemRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  const navContainerRef = useRef<HTMLElement>(null)
  const [indicator, setIndicator] = useState<IndicatorStyle>({ top: 0, height: 0, visible: false })

  // /docs 경로에 있으면 자동으로 docs 섹션 펼치기
  useEffect(() => {
    if (pathname.startsWith("/docs")) {
      setDocsOpen(true)
    }
  }, [pathname])

  const toggleNode = (nodeName: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev)
      if (next.has(nodeName)) next.delete(nodeName)
      else next.add(nodeName)
      return next
    })
  }

  const fetchVms = useCallback(async () => {
    try {
      if (isAdmin) {
        const data = await getAllVms()
        setAdminNodes(data)
      } else {
        const data = await getMyVms()
        setVms(data)
      }
    } catch {
      // 인증 전이면 무시
    } finally {
      setVmLoading(false)
    }
  }, [isAdmin])

  useEffect(() => {
    fetchVms()
    const interval = setInterval(fetchVms, 15000)
    return () => clearInterval(interval)
  }, [fetchVms])

  const isItemActive = (href: string) => {
    if (href === "#") return false
    // /instances는 VM 상세(/instances/123)와 겹치지 않도록 정확 매칭만
    if (href === "/instances") return pathname === "/instances"
    return pathname === href || pathname.startsWith(href + "/")
  }

  // 인디케이터 대상: 메인 메뉴 + VM 목록만 (문서는 제외)
  // 어드민은 node:vmid 조합으로 고유 식별 (같은 vmid가 다른 노드에 존재 가능)
  const allVmKeys = isAdmin
    ? adminNodes.flatMap((n) => n.vms.map((vm) => `${n.name}:/instances/${vm.vmid}`))
    : vms.map((vm) => `/instances/${vm.vmid}`)
  const indicatorHrefs = [
    ...mainNavItems.map((i) => i.href),
    ...(isAdmin ? ["/admin/approvals"] : []),
    ...allVmKeys,
  ]
  const activeHref = indicatorHrefs.find((key) => {
    if (key.includes(":/instances/")) {
      const [node, href] = key.split(":")
      return isItemActive(href) && currentNode === node
    }
    return isItemActive(key)
  })

  // 인디케이터 위치 계산
  const updateIndicator = useCallback(() => {
    if (!activeHref || !navContainerRef.current) {
      setIndicator((prev) => ({ ...prev, visible: false }))
      return
    }

    // 접힌 노드 안의 VM이면 숨김
    if (activeHref.includes(":/instances/")) {
      const [node] = activeHref.split(":")
      if (!expandedNodes.has(node)) {
        setIndicator((prev) => ({ ...prev, visible: false }))
        return
      }
    }

    const el = itemRefs.current.get(activeHref)
    if (!el) {
      setIndicator((prev) => ({ ...prev, visible: false }))
      return
    }

    const container = navContainerRef.current
    const containerRect = container.getBoundingClientRect()
    const elRect = el.getBoundingClientRect()

    if (elRect.height === 0) return

    setIndicator({
      top: elRect.top - containerRect.top + container.scrollTop,
      height: elRect.height,
      visible: true,
    })
  }, [activeHref, expandedNodes])

  useLayoutEffect(() => {
    let rafId: number
    let startTime: number | null = null
    const duration = 320

    const loop = (time: number) => {
      if (startTime === null) startTime = time
      updateIndicator()
      if (time - startTime < duration) {
        rafId = requestAnimationFrame(loop)
      }
    }

    rafId = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(rafId)
  }, [updateIndicator, pathname, vms, adminNodes, currentNode, expandedNodes, docsOpen])

  useEffect(() => {
    window.addEventListener("resize", updateIndicator)
    return () => window.removeEventListener("resize", updateIndicator)
  }, [updateIndicator])

  const getItemRef = useCallback(
    (href: string) => (el: HTMLDivElement | null) => {
      if (el) {
        itemRefs.current.set(href, el)
      } else {
        itemRefs.current.delete(href)
      }
    },
    []
  )

  const isDocsActive = pathname.startsWith("/docs")

  const makeSidebarContent = (withRefs: boolean) => (
    <div className="flex h-full flex-col">
        {/* Logo */}
        <div className="flex h-14 items-center gap-2.5 px-4 mt-3">
          <Image src={gsmsvLogo} alt="GSMSV" width={36} height={36} className="rounded-xl dark:invert" />
          <span className="text-base font-semibold text-sidebar-foreground">
            GSM SV
          </span>
        </div>

        {/* Navigation */}
        <nav ref={withRefs ? navContainerRef : undefined} className="relative flex-1 overflow-y-auto overflow-x-hidden py-4 sidebar-scroll">
          <SlidingIndicator style={indicator} />

          {/* 메뉴 */}
          <div className="mb-6">
            <p className="mb-2 px-4 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Menu
            </p>
            <div className="space-y-0.5">
              {mainNavItems.map((item) => (
                <NavItem
                  key={item.title}
                  item={item}
                  isActive={isItemActive(item.href)}
                  itemRef={withRefs ? getItemRef(item.href) : () => {}}
                />
              ))}
            </div>
          </div>

          {/* Docs — 토글 섹션 */}
          <div className="mb-6">
            <p className="mb-2 px-4 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Docs
            </p>
            <button
              onClick={() => setDocsOpen(!docsOpen)}
              className={cn(
                "flex w-full items-center gap-3 px-4 py-3 text-[14px] font-medium transition-all duration-200 mx-2",
                "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 rounded-lg",
                isDocsActive && "text-sidebar-foreground/90"
              )}
              style={{ width: "calc(100% - 16px)" }}
            >
              <Book className={cn("h-5 w-5 transition-colors", isDocsActive ? "text-white" : "")} />
              <span className="flex-1 text-left">문서</span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 transition-transform duration-200",
                  docsOpen ? "rotate-180" : ""
                )}
              />
            </button>
            <div
              className={cn(
                "overflow-hidden transition-all duration-300 ease-in-out",
                docsOpen ? "max-h-[500px] opacity-100" : "max-h-0 opacity-0"
              )}
            >
              <div className="mt-1 ml-[38px] mr-2">
                {docCategories.map((cat, idx) => {
                  const Icon = cat.icon
                  const active = isItemActive(cat.href)
                  const childActive = cat.children?.some((c) => isItemActive(c.href)) ?? false
                  const isLast = idx === docCategories.length - 1
                  return (
                    <div key={cat.href} className="relative flex">
                      {/* 메인 세로선 (children 포함 전체 높이) */}
                      <div className="relative w-5 shrink-0">
                        <div
                          className="absolute left-0 w-px bg-sidebar-border"
                          style={{ top: 0, height: isLast ? "18px" : "100%" }}
                        />
                        {/* 가로 브랜치 — 링크 첫 행 중앙 */}
                        <div
                          className="absolute left-0 h-px bg-sidebar-border"
                          style={{ top: 18, width: "100%" }}
                        />
                      </div>
                      <div className="flex-1 min-w-0">
                        <Link
                          href={cat.href}
                          className={cn(
                            "flex items-center gap-2.5 px-2.5 py-2 text-[13px] rounded-md transition-all duration-200",
                            active || childActive
                              ? "bg-sidebar-accent text-sidebar-foreground font-medium"
                              : "text-sidebar-foreground/50 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                          )}
                        >
                          <Icon className={cn("h-4 w-4 shrink-0 transition-colors", active || childActive ? "text-white" : "")} />
                          <span>{cat.title}</span>
                        </Link>
                        {/* 하위 카테고리 */}
                        {cat.children && (
                          <div className="ml-3">
                            {cat.children.map((child, childIdx) => {
                              const ChildIcon = child.icon
                              const childIsActive = isItemActive(child.href)
                              const isChildLast = childIdx === cat.children!.length - 1
                              return (
                                <div key={child.href} className="relative flex">
                                  <div className="relative w-5 shrink-0">
                                    <div
                                      className="absolute left-0 w-px bg-sidebar-border"
                                      style={{ top: 0, height: isChildLast ? "50%" : "100%" }}
                                    />
                                    <div
                                      className="absolute left-0 top-1/2 h-px bg-sidebar-border"
                                      style={{ width: "100%" }}
                                    />
                                  </div>
                                  <Link
                                    href={child.href}
                                    className={cn(
                                      "flex flex-1 items-center gap-2.5 px-2.5 py-1.5 text-[12px] rounded-md transition-all duration-200",
                                      childIsActive
                                        ? "bg-sidebar-accent text-sidebar-foreground font-medium"
                                        : "text-sidebar-foreground/40 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                                    )}
                                  >
                                    <ChildIcon className={cn("h-3.5 w-3.5 shrink-0 transition-colors", childIsActive ? "text-white" : "")} />
                                    <span>{child.label ?? child.title}</span>
                                  </Link>
                                </div>
                              )
                            })}
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          {/* 어드민: 승인 관리 */}
          {isAdmin && (
            <div className="mb-6">
              <p className="mb-2 px-4 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Admin
              </p>
              <div className="space-y-0.5">
                <NavItem
                  item={{ title: "가입 승인", href: "/admin/approvals", icon: UserCheck }}
                  isActive={isItemActive("/admin/approvals")}
                  itemRef={withRefs ? getItemRef("/admin/approvals") : () => {}}
                />
              </div>
            </div>
          )}

          {/* 어드민: NODES / 일반: MY VM */}
          {isAdmin ? (
            <div className="mb-6">
              <p className="mb-2 px-4 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Nodes
              </p>
              <div className="space-y-0.5 px-2">
                {vmLoading ? (
                  <div className="flex items-center justify-center py-3">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  </div>
                ) : adminNodes.length === 0 ? (
                  <p className="px-5 py-3 text-sm text-muted-foreground">
                    노드 없음
                  </p>
                ) : (
                  adminNodes.map((node) => (
                    <div key={node.name}>
                      <button
                        onClick={() => toggleNode(node.name)}
                        className="flex w-full items-center gap-3 px-4 py-2.5 text-[13px] font-medium text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 rounded-lg transition-all duration-200"
                      >
                        <Server className="h-4 w-4 shrink-0" />
                        <span className="flex-1 text-left">{node.name}</span>
                        <span className="text-xs text-muted-foreground">{node.vms.length}</span>
                        <ChevronDown
                          className={cn(
                            "h-4 w-4 transition-transform duration-200",
                            expandedNodes.has(node.name) ? "rotate-180" : ""
                          )}
                        />
                      </button>
                      <div
                        className={cn(
                          "overflow-hidden transition-all duration-200",
                          expandedNodes.has(node.name) ? "max-h-[1000px] opacity-100" : "max-h-0 opacity-0"
                        )}
                      >
                        {node.vms.length === 0 ? (
                          <p className="px-12 py-2 text-xs text-muted-foreground">VM 없음</p>
                        ) : (
                          node.vms.map((vm) => {
                            const href = `/instances/${vm.vmid}`
                            const vmKey = `${vm.node}:${href}`
                            const active = (pathname === href || pathname.startsWith(href + "/")) && currentNode === vm.node
                            return (
                              <div
                                key={`${vm.node}-${vm.vmid}`}
                                ref={withRefs ? getItemRef(vmKey) : undefined}
                                className="relative"
                              >
                                <Link
                                  href={`${href}?node=${vm.node}`}
                                  title={`${vm.name}${vm.owner_email ? ` (${vm.owner_email.split("@")[0]})` : ""}`}
                                  className={cn(
                                    "flex items-center gap-3 pl-10 pr-3 py-2 text-[13px] font-medium rounded-lg transition-all duration-200 z-[1] relative",
                                    active
                                      ? "text-orange-400 rounded-l-xl"
                                      : "text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
                                  )}
                                >
                                  <Monitor className={cn("h-4 w-4 shrink-0", active ? "text-orange-400" : "")} />
                                  <div className="truncate flex-1">
                                    <span>{vm.name}</span>
                                    {vm.owner_email && (
                                      <span className="text-[11px] text-muted-foreground ml-1.5">
                                        {vm.owner_email.split("@")[0]}
                                      </span>
                                    )}
                                  </div>
                                  <VmStatusDot status={vm.status || "stopped"} />
                                </Link>
                              </div>
                            )
                          })
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            <div className="mb-6">
              <p className="mb-2 px-4 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                My VM
              </p>
              <div className="space-y-0.5 px-2">
                {vmLoading ? (
                  <div className="flex items-center justify-center py-3">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  </div>
                ) : vms.length === 0 ? (
                  <p className="px-5 py-3 text-sm text-muted-foreground">
                    인스턴스 없음
                  </p>
                ) : (
                  vms.map((vm) => {
                    const href = `/instances/${vm.vmid}`
                    const isActive = pathname === href || pathname.startsWith(href + "/")
                    return (
                      <div
                        key={`${vm.node}-${vm.vmid}`}
                        ref={withRefs ? getItemRef(href) : undefined}
                        className="relative"
                      >
                        <Link
                          href={`${href}?node=${vm.node}`}
                          className={cn(
                            "flex items-center gap-3 px-4 py-3 text-[14px] font-medium rounded-lg transition-all duration-200 z-[1] relative",
                            isActive
                              ? "text-orange-400 rounded-l-xl ml-2"
                              : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50 mx-2"
                          )}
                        >
                          <Monitor className={cn("h-4.5 w-4.5 shrink-0", isActive ? "text-orange-400" : "")} />
                          <span className="truncate flex-1">{vm.name}</span>
                          <VmStatusDot status={vm.status || "stopped"} />
                        </Link>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </nav>

        {/* Footer */}
        <div className="border-t border-sidebar-border p-3">
          <div className="space-y-0.5">
            {footerNavItems.map((item) => {
              const Icon = item.icon
              const active = isItemActive(item.href)
              const cls = cn(
                "flex items-center gap-2.5 px-3 py-2.5 text-[13px] font-medium rounded-lg transition-all duration-200",
                active
                  ? "text-sidebar-foreground bg-sidebar-accent"
                  : "text-sidebar-foreground/70 hover:text-sidebar-foreground hover:bg-sidebar-accent/50"
              )
              if (item.external) {
                return (
                  <a key={item.title} href={item.href} target="_blank" rel="noopener noreferrer" className={cls}>
                    <Icon className="h-4.5 w-4.5" />
                    <span>{item.title}</span>
                  </a>
                )
              }
              return (
                <Link key={item.title} href={item.href} className={cls}>
                  <Icon className={cn("h-4.5 w-4.5 transition-colors", active ? "text-foreground" : "")} />
                  <span>{item.title}</span>
                </Link>
              )
            })}
          </div>
        </div>
    </div>
  )

  return (
    <>
      <aside className="fixed left-0 top-0 z-40 h-screen w-52 bg-sidebar hidden md:block">
        {makeSidebarContent(true)}
      </aside>
      <Sheet open={mobileOpen} onOpenChange={(open) => !open && onMobileClose?.()}>
        <SheetContent side="left" className="w-52 p-0 bg-sidebar border-r border-sidebar-border [&>button]:hidden">
          <SheetTitle className="sr-only">사이드바 메뉴</SheetTitle>
          <button
            onClick={onMobileClose}
            className="absolute right-2 top-2 z-50 rounded-sm p-1 text-sidebar-foreground opacity-70 hover:opacity-100"
            aria-label="닫기"
          >
            <X className="h-4 w-4" />
          </button>
          {makeSidebarContent(false)}
        </SheetContent>
      </Sheet>
    </>
  )
}
