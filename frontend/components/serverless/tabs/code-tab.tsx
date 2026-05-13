"use client"

import { useState } from "react"
import dynamic from "next/dynamic"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { updateFunction, type ServerlessFunction } from "@/lib/serverless-api"

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false })

interface CodeTabProps {
  func: ServerlessFunction
  onUpdate: (func: ServerlessFunction) => void
}

export default function CodeTab({ func, onUpdate }: CodeTabProps) {
  const [code, setCode] = useState(func.code)
  const [runtime, setRuntime] = useState(func.runtime)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await updateFunction(func.id, { code, runtime })
      onUpdate(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="space-y-4 pt-4">
      <div className="flex items-center justify-between">
        <Select
          value={runtime}
          onValueChange={(v: "javascript" | "typescript") => setRuntime(v)}
        >
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="javascript">JavaScript</SelectItem>
            <SelectItem value="typescript">TypeScript</SelectItem>
          </SelectContent>
        </Select>
        <Button onClick={handleSave} disabled={saving} size="sm">
          {saved ? "저장됨 ✓" : saving ? "저장 중..." : "저장"}
        </Button>
      </div>
      <div className="border rounded-md overflow-hidden h-[500px]">
        <MonacoEditor
          height="100%"
          language={runtime === "typescript" ? "typescript" : "javascript"}
          value={code}
          onChange={(val) => setCode(val || "")}
          theme="vs-dark"
          options={{ minimap: { enabled: false }, fontSize: 14, tabSize: 2 }}
        />
      </div>
    </div>
  )
}
