"use client"

import { useEffect, useState } from "react"
import { RefreshCw, Trash2, ChevronDown } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import {
  getFunctionLogs,
  deleteFunctionLogs,
  type ExecutionLog,
} from "@/lib/serverless-api"

interface LogsTabProps {
  funcId: string
}

export default function LogsTab({ funcId }: LogsTabProps) {
  const [logs, setLogs] = useState<ExecutionLog[]>([])
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    getFunctionLogs(funcId)
      .then(setLogs)
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
  }, [funcId])

  const handleClear = async () => {
    await deleteFunctionLogs(funcId)
    setLogs([])
  }

  const statusBadge = (status: string) => {
    const variants: Record<string, "default" | "destructive" | "secondary"> = {
      success: "default",
      error: "destructive",
      timeout: "secondary",
    }
    const labels: Record<string, string> = {
      success: "성공",
      error: "에러",
      timeout: "타임아웃",
    }
    return (
      <Badge variant={variants[status] ?? "default"}>{labels[status] ?? status}</Badge>
    )
  }

  return (
    <div className="space-y-4 pt-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium">실행 로그 ({logs.length})</h3>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className="w-4 h-4 mr-2" />
            새로고침
          </Button>
          <Button variant="outline" size="sm" onClick={handleClear}>
            <Trash2 className="w-4 h-4 mr-2 text-destructive" />
            전체 삭제
          </Button>
        </div>
      </div>

      {loading ? (
        <p className="text-muted-foreground text-sm">로딩 중...</p>
      ) : logs.length === 0 ? (
        <p className="text-muted-foreground text-sm">실행 로그가 없습니다.</p>
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <Collapsible key={log.id}>
              <CollapsibleTrigger asChild>
                <div className="flex items-center justify-between p-3 border rounded-lg cursor-pointer hover:bg-muted/50">
                  <div className="flex items-center gap-3">
                    {statusBadge(log.status)}
                    <Badge variant="outline" className="text-xs">
                      {log.trigger}
                    </Badge>
                    <span className="text-xs text-muted-foreground">{log.duration}ms</span>
                    <span className="text-xs text-muted-foreground">
                      {new Date(log.createdAt).toLocaleString("ko-KR")}
                    </span>
                  </div>
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                </div>
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="p-3 border border-t-0 rounded-b-lg bg-muted/30 space-y-2">
                  {log.error && (
                    <div>
                      <p className="text-xs font-medium text-destructive mb-1">에러</p>
                      <pre className="text-xs text-destructive bg-destructive/10 p-2 rounded overflow-x-auto">
                        {log.error}
                      </pre>
                    </div>
                  )}
                  {log.logs.length > 0 && (
                    <div>
                      <p className="text-xs font-medium mb-1">출력 로그</p>
                      <pre className="text-xs bg-background p-2 rounded border overflow-x-auto">
                        {log.logs.join("\n")}
                      </pre>
                    </div>
                  )}
                  {log.response && (
                    <div>
                      <p className="text-xs font-medium mb-1">응답</p>
                      <pre className="text-xs bg-background p-2 rounded border overflow-x-auto">
                        {log.response}
                      </pre>
                    </div>
                  )}
                </div>
              </CollapsibleContent>
            </Collapsible>
          ))}
        </div>
      )}
    </div>
  )
}
