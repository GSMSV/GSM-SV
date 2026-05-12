"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { Trash2 } from "lucide-react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { getFunction, deleteFunction, type ServerlessFunction } from "@/lib/serverless-api"
import CodeTab from "@/components/serverless/tabs/code-tab"
import TriggersTab from "@/components/serverless/tabs/triggers-tab"
import EnvTab from "@/components/serverless/tabs/env-tab"
import LogsTab from "@/components/serverless/tabs/logs-tab"
import TestTab from "@/components/serverless/tabs/test-tab"

export default function ServerlessFunctionPage() {
  const params = useParams()
  const router = useRouter()
  const id = params.id as string
  const [func, setFunc] = useState<ServerlessFunction | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getFunction(id)
      .then(setFunc)
      .catch(() => router.push("/serverless"))
      .finally(() => setLoading(false))
  }, [id, router])

  const handleDelete = async () => {
    if (!func) return
    try {
      await deleteFunction(func.id)
    } finally {
      router.push("/serverless")
    }
  }

  if (loading || !func) {
    return <div className="text-muted-foreground text-sm">로딩 중...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">{func.name}</h1>
          <Badge variant={func.status === "active" ? "default" : "secondary"}>
            {func.status === "active" ? "활성" : "비활성"}
          </Badge>
          <Badge variant="outline">{func.runtime}</Badge>
        </div>
        <AlertDialog>
          <AlertDialogTrigger asChild>
            <Button variant="outline" size="sm">
              <Trash2 className="w-4 h-4 mr-2 text-destructive" />
              삭제
            </Button>
          </AlertDialogTrigger>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>함수 삭제</AlertDialogTitle>
              <AlertDialogDescription>
                &quot;{func.name}&quot;을 삭제하면 모든 트리거와 로그가 함께 삭제됩니다.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>취소</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDelete}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              >
                삭제
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>

      <Tabs defaultValue="code">
        <TabsList>
          <TabsTrigger value="code">코드</TabsTrigger>
          <TabsTrigger value="triggers">트리거</TabsTrigger>
          <TabsTrigger value="env">환경변수</TabsTrigger>
          <TabsTrigger value="logs">로그</TabsTrigger>
          <TabsTrigger value="test">테스트</TabsTrigger>
        </TabsList>
        <TabsContent value="code">
          <CodeTab func={func} onUpdate={setFunc} />
        </TabsContent>
        <TabsContent value="triggers">
          <TriggersTab funcId={func.id} ownerId={func.ownerId} funcName={func.name} />
        </TabsContent>
        <TabsContent value="env">
          <EnvTab func={func} onUpdate={setFunc} />
        </TabsContent>
        <TabsContent value="logs">
          <LogsTab funcId={func.id} />
        </TabsContent>
        <TabsContent value="test">
          <TestTab funcId={func.id} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
