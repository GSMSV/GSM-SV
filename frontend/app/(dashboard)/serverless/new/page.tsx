"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import dynamic from "next/dynamic"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { createFunction } from "@/lib/serverless-api"

const MonacoEditor = dynamic(() => import("@monaco-editor/react"), { ssr: false })

const JS_TEMPLATE = `export default async function handler(request) {
  return new Response(JSON.stringify({ message: "Hello, World!" }), {
    headers: { "Content-Type": "application/json" },
  });
}`

const TS_TEMPLATE = `export default async function handler(request: Request): Promise<Response> {
  return new Response(JSON.stringify({ message: "Hello, World!" }), {
    headers: { "Content-Type": "application/json" },
  });
}`

export default function NewServerlessPage() {
  const router = useRouter()
  const [name, setName] = useState("")
  const [description, setDescription] = useState("")
  const [runtime, setRuntime] = useState<"javascript" | "typescript">("javascript")
  const [code, setCode] = useState(JS_TEMPLATE)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")

  const handleRuntimeChange = (val: "javascript" | "typescript") => {
    setRuntime(val)
    setCode(val === "typescript" ? TS_TEMPLATE : JS_TEMPLATE)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim() || !code.trim()) {
      setError("이름과 코드는 필수입니다.")
      return
    }
    setLoading(true)
    setError("")
    try {
      const func = await createFunction({
        name: name.trim(),
        description: description.trim() || undefined,
        code,
        runtime,
      })
      router.push(`/serverless/${func.id}`)
    } catch (err: unknown) {
      const e = err as { detail?: string; message?: string }
      setError(e.detail || e.message || "함수 생성에 실패했습니다.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">새 함수 만들기</h1>
        <p className="text-muted-foreground text-sm mt-1">
          JS/TS 코드를 작성하고 배포하세요
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="name">함수 이름 *</Label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="my-function"
            />
          </div>
          <div className="space-y-2">
            <Label>런타임</Label>
            <Select value={runtime} onValueChange={handleRuntimeChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="javascript">JavaScript</SelectItem>
                <SelectItem value="typescript">TypeScript</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="description">설명 (선택)</Label>
          <Textarea
            id="description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
          />
        </div>

        <div className="space-y-2">
          <Label>코드</Label>
          <div className="border rounded-md overflow-hidden h-80">
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

        {error && <p className="text-destructive text-sm">{error}</p>}

        <div className="flex gap-3">
          <Button type="submit" disabled={loading}>
            {loading ? "생성 중..." : "함수 생성"}
          </Button>
          <Button type="button" variant="outline" onClick={() => router.back()}>
            취소
          </Button>
        </div>
      </form>
    </div>
  )
}
