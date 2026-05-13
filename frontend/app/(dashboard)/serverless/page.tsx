"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus, Zap } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip"
import { getFunctions, getQuota, type ServerlessFunction, type FunctionQuota } from "@/lib/serverless-api"
import FunctionList from "@/components/serverless/function-list"

export default function ServerlessPage() {
  const [functions, setFunctions] = useState<ServerlessFunction[]>([])
  const [quota, setQuota] = useState<FunctionQuota | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([getFunctions(), getQuota()])
      .then(([funcs, q]) => {
        setFunctions(funcs)
        setQuota(q)
      })
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const isAtLimit = !quota || functions.length >= quota.max

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">서버리스 함수</h1>
          <p className="text-muted-foreground text-sm mt-1">
            코드를 배포하고 HTTP 트리거 또는 Cron으로 실행하세요
          </p>
        </div>
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={isAtLimit ? 0 : -1}>
              <Button asChild={!isAtLimit} disabled={isAtLimit}>
                {isAtLimit ? (
                  <span className="flex items-center">
                    <Plus className="w-4 h-4 mr-2" />
                    새 함수
                  </span>
                ) : (
                  <Link href="/serverless/new">
                    <Plus className="w-4 h-4 mr-2" />
                    새 함수
                  </Link>
                )}
              </Button>
            </span>
          </TooltipTrigger>
          {isAtLimit && quota && (
            <TooltipContent>
              함수 한도({quota.max}개)에 도달했습니다
            </TooltipContent>
          )}
        </Tooltip>
      </div>

      {quota && (
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium">함수 사용량</span>
            <span className="text-sm text-muted-foreground">
              {quota.current} / {quota.max} 개
            </span>
          </div>
          <div className="w-full bg-muted rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all ${
                quota.current >= quota.max ? "bg-destructive" : "bg-primary"
              }`}
              style={{ width: `${Math.min((quota.current / quota.max) * 100, 100)}%` }}
            />
          </div>
        </div>
      )}

      {loading ? (
        <div className="text-muted-foreground text-sm">로딩 중...</div>
      ) : functions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Zap className="w-12 h-12 text-muted-foreground mb-4" />
          <h2 className="text-lg font-semibold">아직 함수가 없습니다</h2>
          <p className="text-muted-foreground text-sm mt-1 mb-4">
            첫 번째 서버리스 함수를 만들어보세요
          </p>
          <Button asChild>
            <Link href="/serverless/new">
              <Plus className="w-4 h-4 mr-2" />
              함수 만들기
            </Link>
          </Button>
        </div>
      ) : (
        <FunctionList
          functions={functions}
          onDeleted={(id) => setFunctions((prev) => prev.filter((f) => f.id !== id))}
        />
      )}
    </div>
  )
}
