"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { Zap, HardDrive, Terminal, KeyRound, MessageCircleQuestion, MessageSquarePlus, ChevronRight, Code2 } from "lucide-react"

const sideNav = [
  { title: "시작하기", href: "/docs/getting-started", icon: Zap },
  { title: "인스턴스", href: "/docs/instances", icon: HardDrive },
  { title: "접속 방법", href: "/docs/access", icon: Terminal },
  { title: "SSH Key 등록", href: "/docs/ssh-key", icon: KeyRound },
  { title: "Serverless 함수", href: "/docs/serverless", icon: Code2 },
  { title: "FAQ", href: "/docs/faq", icon: MessageCircleQuestion },
  { title: "질문 등록", href: "/docs/questions", icon: MessageSquarePlus },
]

export function DocsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()

  return (
    <div>
      {/* Content */}
      <article className="max-w-3xl mx-auto">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground mb-6">
          <Link href="/docs" className="hover:text-foreground transition-colors">
            Docs
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-foreground font-medium">
            {sideNav.find((n) => n.href === pathname)?.title ?? "문서"}
          </span>
        </div>

        <div className="prose prose-neutral dark:prose-invert max-w-none
          prose-headings:scroll-mt-20 prose-headings:tracking-tight
          prose-h1:text-2xl prose-h1:font-semibold prose-h1:mb-4
          prose-h2:text-xl prose-h2:font-semibold prose-h2:mt-10 prose-h2:mb-3 prose-h2:border-b prose-h2:border-border prose-h2:pb-2
          prose-h3:text-base prose-h3:font-semibold prose-h3:mt-6 prose-h3:mb-2
          prose-p:text-sm prose-p:leading-relaxed prose-p:text-muted-foreground
          prose-li:text-sm prose-li:text-muted-foreground
          prose-strong:text-foreground
          prose-code:text-sm prose-code:bg-muted prose-code:text-foreground prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded-md prose-code:font-mono
          prose-pre:bg-muted prose-pre:text-foreground prose-pre:border prose-pre:border-border prose-pre:rounded-lg prose-pre:px-4 prose-pre:py-3
          [&_pre_code]:p-0 [&_pre_code]:bg-transparent [&_pre_code]:border-0
          prose-table:text-sm
          prose-th:text-left prose-th:font-semibold prose-th:px-4 prose-th:py-2.5 prose-th:bg-muted prose-th:border-b prose-th:border-border
          prose-td:px-4 prose-td:py-2.5 prose-td:border-b prose-td:border-border/50
          prose-blockquote:border-l-primary/50 prose-blockquote:bg-primary/5 prose-blockquote:py-1 prose-blockquote:px-4 prose-blockquote:rounded-r-lg prose-blockquote:not-italic
          prose-a:text-primary prose-a:no-underline hover:prose-a:underline
        ">
          {children}
        </div>

        {/* Page Navigation */}
        <div className="flex items-center justify-between mt-12 pt-6 border-t border-border">
          {(() => {
            const currentIdx = sideNav.findIndex((n) => n.href === pathname)
            const prev = currentIdx > 0 ? sideNav[currentIdx - 1] : null
            const next = currentIdx < sideNav.length - 1 ? sideNav[currentIdx + 1] : null
            return (
              <>
                {prev ? (
                  <Link href={prev.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                    &larr; {prev.title}
                  </Link>
                ) : <div />}
                {next ? (
                  <Link href={next.href} className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                    {next.title} &rarr;
                  </Link>
                ) : <div />}
              </>
            )
          })()}
        </div>
      </article>
    </div>
  )
}
