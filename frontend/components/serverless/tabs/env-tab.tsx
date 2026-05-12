"use client"

import { useState } from "react"
import { Plus, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { updateFunction, type ServerlessFunction } from "@/lib/serverless-api"

interface EnvTabProps {
  func: ServerlessFunction
  onUpdate: (func: ServerlessFunction) => void
}

export default function EnvTab({ func, onUpdate }: EnvTabProps) {
  const [entries, setEntries] = useState<[string, string][]>(Object.entries(func.envVars))
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleAdd = () => setEntries((prev) => [...prev, ["", ""]])
  const handleRemove = (i: number) => setEntries((prev) => prev.filter((_, idx) => idx !== i))
  const handleChange = (i: number, k: string, v: string) => {
    setEntries((prev) => prev.map((entry, idx) => (idx === i ? [k, v] : entry)))
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      const envVars = Object.fromEntries(entries.filter(([k]) => k.trim()))
      const updated = await updateFunction(func.id, { envVars })
      onUpdate(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4 pt-4">
      <p className="text-sm text-muted-foreground">
        함수 내에서 <code className="text-xs bg-muted px-1 rounded">env.KEY</code>로 접근할 수
        있습니다.
      </p>
      <div className="space-y-2">
        {entries.map(([k, v], i) => (
          <div key={i} className="flex gap-2">
            <Input
              value={k}
              onChange={(e) => handleChange(i, e.target.value, v)}
              placeholder="KEY"
              className="font-mono"
            />
            <Input
              value={v}
              onChange={(e) => handleChange(i, k, e.target.value)}
              placeholder="VALUE"
              className="font-mono"
            />
            <Button variant="ghost" size="icon" onClick={() => handleRemove(i)}>
              <Trash2 className="w-4 h-4 text-destructive" />
            </Button>
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={handleAdd}>
          <Plus className="w-4 h-4 mr-2" />
          추가
        </Button>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saved ? "저장됨 ✓" : saving ? "저장 중..." : "저장"}
        </Button>
      </div>
    </div>
  )
}
