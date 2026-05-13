"use client"

import Link from "next/link"
import { Trash2 } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
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
import { deleteFunction, type ServerlessFunction } from "@/lib/serverless-api"

interface FunctionListProps {
  functions: ServerlessFunction[]
  onDeleted: (id: string) => void
}

export default function FunctionList({ functions, onDeleted }: FunctionListProps) {
  const handleDelete = async (id: string) => {
    await deleteFunction(id)
    onDeleted(id)
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {functions.map((func) => (
        <Card key={func.id} className="hover:shadow-md transition-shadow">
          <CardHeader className="pb-2">
            <div className="flex items-start justify-between gap-2">
              <Link href={`/serverless/${func.id}`} className="hover:underline">
                <CardTitle className="text-base">{func.name}</CardTitle>
              </Link>
              <div className="flex items-center gap-2 shrink-0">
                <Badge variant={func.status === "active" ? "default" : "secondary"}>
                  {func.status === "active" ? "활성" : "비활성"}
                </Badge>
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-7 w-7">
                      <Trash2 className="w-3.5 h-3.5 text-destructive" />
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>함수 삭제</AlertDialogTitle>
                      <AlertDialogDescription>
                        &quot;{func.name}&quot; 함수를 삭제하면 모든 트리거와 로그가 함께 삭제됩니다.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>취소</AlertDialogCancel>
                      <AlertDialogAction
                        onClick={() => handleDelete(func.id)}
                        className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                      >
                        삭제
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-muted-foreground line-clamp-2">
              {func.description || "설명 없음"}
            </p>
            <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline" className="text-xs">
                {func.runtime}
              </Badge>
              <span>타임아웃 {func.timeout / 1000}s</span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
