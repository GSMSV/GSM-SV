"use client"

import { useState } from "react"
import { Play } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"
import { executeFunction, type ExecutionResult } from "@/lib/serverless-api"

interface TestTabProps {
  funcId: string
}

export default function TestTab({ funcId }: TestTabProps) {
  const [payload, setPayload] = useState('{\n  "key": "value"\n}')
  const [result, setResult] = useState<ExecutionResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState("")

  const handleRun = async () => {
    setRunning(true)
    setError("")
    try {
      let parsed: unknown = {}
      try {
        parsed = JSON.parse(payload)
      } catch {
        setError("페이로드가 유효한 JSON이 아닙니다.")
        setRunning(false)
        return
      }
      const res = await executeFunction(funcId, parsed)
      setResult(res)
    } catch (err: unknown) {
      const e = err as { detail?: string; message?: string }
      setError(e.detail || e.message || "실행 실패")
    } finally {
      setRunning(false)
    }
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
    <div className="space-y-6 pt-4">
      <div className="space-y-2">
        <Label>요청 페이로드 (JSON)</Label>
        <Textarea
          value={payload}
          onChange={(e) => setPayload(e.target.value)}
          className="font-mono text-sm"
          rows={6}
        />
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <Button onClick={handleRun} disabled={running}>
        <Play className="w-4 h-4 mr-2" />
        {running ? "실행 중..." : "실행"}
      </Button>

      {result && (
        <div className="space-y-3 border rounded-lg p-4">
          <div className="flex items-center gap-3">
            <h4 className="font-medium">실행 결과</h4>
            {statusBadge(result.status)}
            <span className="text-xs text-muted-foreground">{result.duration}ms</span>
            <span className="text-xs text-muted-foreground">HTTP {result.statusCode}</span>
          </div>
          {result.error && (
            <pre className="text-xs text-destructive bg-destructive/10 p-3 rounded overflow-x-auto">
              {result.error}
            </pre>
          )}
          {result.logs.length > 0 && (
            <div>
              <p className="text-xs font-medium mb-1">출력 로그</p>
              <pre className="text-xs bg-muted p-3 rounded overflow-x-auto">
                {result.logs.join("\n")}
              </pre>
            </div>
          )}
          {result.body && (
            <div>
              <p className="text-xs font-medium mb-1">응답 본문</p>
              <pre className="text-xs bg-muted p-3 rounded overflow-x-auto">{result.body}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
