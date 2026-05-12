"use client"

import { useEffect, useState } from "react"
import Link from "next/link"
import { Plus, Zap } from "lucide-react"
import { Button } from "@/components/ui/button"
import { getFunctions, type ServerlessFunction } from "@/lib/serverless-api"
import FunctionList from "@/components/serverless/function-list"

const MAX_FUNCTIONS = 5

export default function ServerlessPage() {
  const [functions, setFunctions] = useState<ServerlessFunction[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getFunctions()
      .then(setFunctions)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">서버리스 함수</h1>
          <p className="text-muted-foreground text-sm mt-1">
            코드를 배포하고 HTTP 트리거 또는 Cron으로 실행하세요
          </p>
        </div>
        <Button asChild disabled={functions.length >= MAX_FUNCTIONS}>
          <Link href="/serverless/new">
            <Plus className="w-4 h-4 mr-2" />
            새 함수
          </Link>
        </Button>
      </div>

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
