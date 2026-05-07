"use client"

import { useState, useRef, useEffect } from "react"
import { requestPasswordReset, confirmPasswordReset, ApiError, type ResetRole } from "@/lib/api"
import Link from "next/link"
import {
  KeyRound, Loader2, Check, Eye, EyeOff, ArrowLeft, RotateCw, Sun, Moon,
} from "lucide-react"
import { useTheme } from "next-themes"

type Step = "email" | "code"

export default function ResetPasswordPage() {
  const { theme, setTheme } = useTheme()
  const themeToggling = useRef(false)

  const toggleTheme = () => {
    if (themeToggling.current) return
    themeToggling.current = true
    setTheme(theme === "dark" ? "light" : "dark")
    setTimeout(() => { themeToggling.current = false }, 400)
  }

  const [step, setStep] = useState<Step>("email")
  const [email, setEmail] = useState("")
  const [loginRole, setLoginRole] = useState<ResetRole>("user")
  const [emailLoading, setEmailLoading] = useState(false)

  // Step 2
  const [code, setCode] = useState(["", "", "", "", "", ""])
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [submitLoading, setSubmitLoading] = useState(false)
  const [resending, setResending] = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)

  const [error, setError] = useState("")
  const [success, setSuccess] = useState(false)

  const passwordChecks = [
    { label: "8자 이상", pass: newPassword.length >= 8 },
    { label: "영문 포함", pass: /[a-zA-Z]/.test(newPassword) },
    { label: "숫자 포함", pass: /\d/.test(newPassword) },
    { label: "특수문자 포함", pass: /[!@#$%^&*()_+\-=\[\]{}|;:'",.<>?/~`]/.test(newPassword) },
  ]
  const passwordStrength = passwordChecks.filter((c) => c.pass).length
  const passwordTotal = passwordChecks.length

  useEffect(() => {
    if (resendCooldown <= 0) return
    const timer = setTimeout(() => setResendCooldown(resendCooldown - 1), 1000)
    return () => clearTimeout(timer)
  }, [resendCooldown])

  // Step 1: 이메일 입력 → 코드 발송
  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setEmailLoading(true)
    try {
      await requestPasswordReset(email, loginRole)
      setStep("code")
      setResendCooldown(60)
      setTimeout(() => inputRefs.current[0]?.focus(), 100)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail)
      } else {
        setError("요청 중 오류가 발생했습니다.")
      }
    } finally {
      setEmailLoading(false)
    }
  }

  // 코드 입력 핸들러
  const handleChange = (index: number, value: string) => {
    if (value && !/^\d$/.test(value)) return
    const newCode = [...code]
    newCode[index] = value
    setCode(newCode)
    setError("")
    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pasted = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6)
    if (!pasted) return
    const newCode = [...code]
    for (let i = 0; i < 6; i++) {
      newCode[i] = pasted[i] || ""
    }
    setCode(newCode)
    setError("")
    const focusIndex = Math.min(pasted.length, 5)
    inputRefs.current[focusIndex]?.focus()
  }

  // 재발송
  const handleResend = async () => {
    if (resending || resendCooldown > 0) return
    setResending(true)
    setError("")
    try {
      await requestPasswordReset(email, loginRole)
      setResendCooldown(60)
      setCode(["", "", "", "", "", ""])
      inputRefs.current[0]?.focus()
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail)
      } else {
        setError("코드 재발송에 실패했습니다.")
      }
    } finally {
      setResending(false)
    }
  }

  // Step 2: 코드 + 새 비밀번호 → 재설정 완료
  const handleConfirmReset = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    const fullCode = code.join("")
    if (fullCode.length !== 6) {
      setError("6자리 인증 코드를 모두 입력해주세요.")
      return
    }
    if (newPassword !== confirmPassword) {
      setError("비밀번호가 일치하지 않습니다.")
      return
    }
    if (passwordStrength < passwordTotal) {
      setError("비밀번호 조건을 모두 충족해주세요.")
      return
    }

    setSubmitLoading(true)
    try {
      await confirmPasswordReset(email, fullCode, newPassword, loginRole)
      setSuccess(true)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail)
      } else {
        setError("비밀번호 재설정 중 오류가 발생했습니다.")
      }
    } finally {
      setSubmitLoading(false)
    }
  }

  // 성공 화면
  if (success) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-[420px] space-y-8 text-center">
          <div className="flex flex-col items-center space-y-4">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10">
              <Check className="h-7 w-7 text-emerald-500" />
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-foreground">비밀번호 변경 완료</h1>
            <p className="text-sm text-muted-foreground">
              새 비밀번호로 로그인해주세요.
            </p>
          </div>
          <Link
            href="/login"
            className="flex h-12 w-full items-center justify-center rounded-xl bg-foreground text-sm font-semibold text-background hover:opacity-90"
          >
            로그인으로 이동
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      {/* 테마 토글 */}
      <button
        onClick={toggleTheme}
        className="absolute top-6 right-6 flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground hover:text-foreground transition-colors"
      >
        <Sun className="h-4 w-4 rotate-0 scale-100 dark:-rotate-90 dark:scale-0" style={{ transition: "transform 0.35s ease, opacity 0.35s ease" }} />
        <Moon className="absolute h-4 w-4 rotate-90 scale-0 dark:rotate-0 dark:scale-100" style={{ transition: "transform 0.35s ease, opacity 0.35s ease" }} />
      </button>

      <div className="w-full max-w-[420px] space-y-8">
        {/* 로고 + 헤더 */}
        <div className="flex flex-col items-center space-y-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted">
            <KeyRound className="h-7 w-7 text-muted-foreground" />
          </div>
          <div className="text-center space-y-1">
            <h1 className="text-2xl font-bold tracking-tight text-foreground">
              {step === "email" ? "비밀번호 재설정" : "새 비밀번호 설정"}
            </h1>
            <p className="text-sm text-muted-foreground">
              {step === "email"
                ? "가입한 이메일을 입력하면 인증 코드를 보내드립니다"
                : `${email}으로 발송된 코드와 새 비밀번호를 입력해주세요`
              }
            </p>
          </div>
        </div>

        {/* 에러 */}
        {error && (
          <div className="flex items-center gap-2 rounded-xl border border-destructive/20 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            <div className="h-2 w-2 shrink-0 rounded-full bg-destructive" />
            {error}
          </div>
        )}

        {/* Step 1: 이메일 입력 */}
        {step === "email" && (
          <div className="space-y-5">
            {/* 역할 선택 탭 */}
            <div className="relative flex rounded-xl border border-border bg-muted/50 p-1">
              <div
                className="absolute top-1 bottom-1 rounded-lg bg-background shadow-sm transition-all duration-300 ease-in-out"
                style={{
                  width: "calc(50% - 4px)",
                  left: loginRole === "user" ? "4px" : "calc(50% + 0px)",
                }}
              />
              <button
                type="button"
                onClick={() => { setLoginRole("user"); setError(""); }}
                className={`relative z-10 flex-1 rounded-lg py-2 text-sm font-medium cursor-pointer transition-colors duration-200 ${
                  loginRole === "user"
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                일반
              </button>
              <button
                type="button"
                onClick={() => { setLoginRole("project_owner"); setError(""); }}
                className={`relative z-10 flex-1 rounded-lg py-2 text-sm font-medium cursor-pointer transition-colors duration-200 ${
                  loginRole === "project_owner"
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                프로젝트 오너
              </button>
            </div>

            <form onSubmit={handleRequestReset} className="space-y-5">
              <div className="space-y-2">
                <label htmlFor="email" className="text-sm font-medium text-foreground">
                  이메일
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="your@gsm.hs.kr"
                  autoComplete="email"
                  className="flex h-12 w-full rounded-xl border border-input bg-card px-4 text-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent"
                />
              </div>

              <button
                type="submit"
                disabled={emailLoading || !email}
                className="relative flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-foreground text-sm font-semibold text-background hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed fast-theme"
              >
                {emailLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    발송 중...
                  </>
                ) : (
                  "인증 코드 발송"
                )}
              </button>
            </form>

            <div className="text-center">
              <Link
                href="/login"
                className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                로그인으로 돌아가기
              </Link>
            </div>
          </div>
        )}

        {/* Step 2: 코드 + 새 비밀번호 */}
        {step === "code" && (
          <form onSubmit={handleConfirmReset} className="space-y-6">
            {/* 6자리 코드 */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-foreground">인증 코드</label>
              <div className="flex justify-center gap-3" onPaste={handlePaste}>
                {code.map((digit, i) => (
                  <input
                    key={i}
                    ref={(el) => { inputRefs.current[i] = el }}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    value={digit}
                    onChange={(e) => handleChange(i, e.target.value)}
                    onKeyDown={(e) => handleKeyDown(i, e)}
                    className="flex h-14 w-12 items-center justify-center rounded-xl border border-input bg-card text-center text-xl font-bold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent"
                  />
                ))}
              </div>
              <div className="text-center">
                <button
                  type="button"
                  onClick={handleResend}
                  disabled={resending || resendCooldown > 0}
                  className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <RotateCw className={`h-3 w-3 ${resending ? "animate-spin" : ""}`} />
                  {resendCooldown > 0
                    ? `${resendCooldown}초 후 재발송`
                    : resending
                    ? "발송 중..."
                    : "코드 재발송"
                  }
                </button>
              </div>
            </div>

            {/* 새 비밀번호 */}
            <div className="space-y-2">
              <label htmlFor="new-password" className="text-sm font-medium text-foreground">
                새 비밀번호
              </label>
              <div className="relative">
                <input
                  id="new-password"
                  type={showPassword ? "text" : "password"}
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="새 비밀번호를 입력하세요"
                  autoComplete="new-password"
                  className="flex h-12 w-full rounded-xl border border-input bg-card px-4 pr-12 text-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              {newPassword.length > 0 && (
                <div className="space-y-2 pt-1">
                  <div className="flex gap-1.5">
                    {Array.from({ length: passwordTotal }, (_, i) => i + 1).map((level) => (
                      <div
                        key={level}
                        className="h-1 flex-1 rounded-full transition-colors"
                        style={{
                          background:
                            passwordStrength >= level
                              ? passwordStrength === passwordTotal
                                ? "var(--status-active-dot)"
                                : passwordStrength >= passwordTotal - 1
                                ? "var(--status-pending-dot)"
                                : "var(--status-error-dot)"
                              : "var(--muted)",
                        }}
                      />
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    {passwordChecks.map((check, i) => (
                      <span
                        key={i}
                        className="flex items-center gap-1 text-xs"
                        style={{
                          color: check.pass ? "var(--status-active-fg)" : "var(--muted-foreground)",
                        }}
                      >
                        {check.pass ? <Check className="h-3 w-3" /> : <div className="h-3 w-3 rounded-full border border-current" />}
                        {check.label}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* 비밀번호 확인 */}
            <div className="space-y-2">
              <label htmlFor="confirm-password" className="text-sm font-medium text-foreground">
                비밀번호 확인
              </label>
              <input
                id="confirm-password"
                type="password"
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="비밀번호를 다시 입력하세요"
                autoComplete="new-password"
                className="flex h-12 w-full rounded-xl border border-input bg-card px-4 text-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-transparent"
              />
              {confirmPassword.length > 0 && newPassword !== confirmPassword && (
                <p className="text-xs" style={{ color: "var(--status-error-fg)" }}>
                  비밀번호가 일치하지 않습니다
                </p>
              )}
            </div>

            {/* 버튼 */}
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => { setStep("email"); setError(""); setCode(["", "", "", "", "", ""]); }}
                className="flex h-12 items-center justify-center gap-2 rounded-xl border border-border bg-card px-5 text-sm font-medium text-foreground hover:bg-muted transition-colors"
              >
                <ArrowLeft className="h-4 w-4" />
                이전
              </button>
              <button
                type="submit"
                disabled={submitLoading}
                className="relative flex h-12 flex-1 items-center justify-center gap-2 rounded-xl bg-foreground text-sm font-semibold text-background hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed fast-theme"
              >
                {submitLoading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    변경 중...
                  </>
                ) : (
                  "비밀번호 변경"
                )}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
