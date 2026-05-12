"use client"

import { useEffect, useState } from "react"
import { Plus, Trash2, Globe, Clock } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  getTriggers,
  createTrigger,
  updateTrigger,
  deleteTrigger,
  type FunctionTrigger,
} from "@/lib/serverless-api"

interface TriggersTabProps {
  funcId: string
  ownerId: number
  funcName: string
}

export default function TriggersTab({ funcId, ownerId, funcName }: TriggersTabProps) {
  const [triggers, setTriggers] = useState<FunctionTrigger[]>([])
  const [open, setOpen] = useState(false)
  const [type, setType] = useState<"http" | "cron">("http")
  const [httpMethod, setHttpMethod] = useState("ANY")
  const [cronExpr, setCronExpr] = useState("*/5 * * * *")
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    getTriggers(funcId).then(setTriggers)
  }, [funcId])

  const handleCreate = async () => {
    setCreating(true)
    try {
      const trigger = await createTrigger(funcId, {
        type,
        httpMethod: type === "http" ? httpMethod : undefined,
        cronExpr: type === "cron" ? cronExpr : undefined,
      })
      setTriggers((prev) => [...prev, trigger])
      setOpen(false)
    } finally {
      setCreating(false)
    }
  }

  const handleToggle = async (trigger: FunctionTrigger) => {
    const updated = await updateTrigger(funcId, trigger.id, { enabled: !trigger.enabled })
    setTriggers((prev) => prev.map((t) => (t.id === trigger.id ? updated : t)))
  }

  const handleDelete = async (id: string) => {
    await deleteTrigger(funcId, id)
    setTriggers((prev) => prev.filter((t) => t.id !== id))
  }

  return (
    <div className="space-y-4 pt-4">
      <div className="flex justify-between items-center">
        <h3 className="font-medium">트리거 목록</h3>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="w-4 h-4 mr-2" />
              트리거 추가
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>트리거 추가</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div className="space-y-2">
                <Label>트리거 타입</Label>
                <Select value={type} onValueChange={(v: "http" | "cron") => setType(v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="http">HTTP 트리거</SelectItem>
                    <SelectItem value="cron">Cron 트리거</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              {type === "http" ? (
                <div className="space-y-2">
                  <Label>HTTP 메서드</Label>
                  <Select value={httpMethod} onValueChange={setHttpMethod}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ANY">ANY</SelectItem>
                      <SelectItem value="GET">GET</SelectItem>
                      <SelectItem value="POST">POST</SelectItem>
                    </SelectContent>
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    URL: fn.gsmsv.site/{ownerId}/{funcName}
                  </p>
                </div>
              ) : (
                <div className="space-y-2">
                  <Label>Cron 표현식</Label>
                  <Input
                    value={cronExpr}
                    onChange={(e) => setCronExpr(e.target.value)}
                    placeholder="*/5 * * * *"
                  />
                  <p className="text-xs text-muted-foreground">
                    예: &#42;/5 &#42; &#42; &#42; &#42; (5분마다), 0 9 &#42; &#42; &#42; (매일 오전 9시)
                  </p>
                </div>
              )}
              <Button onClick={handleCreate} disabled={creating} className="w-full">
                {creating ? "추가 중..." : "추가"}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {triggers.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          트리거가 없습니다. 트리거를 추가하면 함수가 자동으로 실행됩니다.
        </p>
      ) : (
        <div className="space-y-2">
          {triggers.map((trigger) => (
            <div
              key={trigger.id}
              className="flex items-center justify-between p-3 border rounded-lg"
            >
              <div className="flex items-center gap-3">
                {trigger.type === "http" ? (
                  <Globe className="w-4 h-4 text-blue-500" />
                ) : (
                  <Clock className="w-4 h-4 text-green-500" />
                )}
                <div>
                  <div className="text-sm font-medium flex items-center gap-2">
                    {trigger.type === "http" ? (
                      <span>HTTP ({trigger.httpMethod})</span>
                    ) : (
                      <span>
                        Cron:{" "}
                        <code className="text-xs bg-muted px-1 rounded">{trigger.cronExpr}</code>
                      </span>
                    )}
                    <Badge
                      variant={trigger.enabled ? "default" : "secondary"}
                      className="text-xs"
                    >
                      {trigger.enabled ? "활성" : "비활성"}
                    </Badge>
                  </div>
                  {trigger.type === "http" && (
                    <p className="text-xs text-muted-foreground">
                      fn.gsmsv.site/{ownerId}/{funcName}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={trigger.enabled}
                  onCheckedChange={() => handleToggle(trigger)}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => handleDelete(trigger.id)}
                >
                  <Trash2 className="w-3.5 h-3.5 text-destructive" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
