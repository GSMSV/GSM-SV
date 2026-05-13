"use client"

import { DocsLayout } from "@/components/docs/docs-layout"

export default function ServerlessPage() {
  return (
    <DocsLayout>
      <h1>Serverless 함수</h1>

      <h2>개요</h2>
      <p>
        <strong>GSM SV Serverless</strong>는 별도의 서버 없이 JavaScript 또는 TypeScript 코드를 클라우드에서 바로 실행할 수 있는 함수 실행 서비스입니다.
        각 함수는 <code>isolated-vm</code> 샌드박스에서 독립적으로 실행되어 다른 사용자의 코드와 완전히 격리됩니다.
      </p>
      <p>
        HTTP 요청이나 크론 스케줄로 함수를 트리거할 수 있으며, 실행 로그와 결과를 콘솔에서 바로 확인할 수 있습니다.
      </p>

      <h2>제한 사항</h2>
      <table>
        <thead>
          <tr>
            <th>항목</th>
            <th>기본값</th>
            <th>최대값</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>계정당 함수 수</td>
            <td>—</td>
            <td>5개</td>
          </tr>
          <tr>
            <td>실행 타임아웃</td>
            <td>30,000ms</td>
            <td>60,000ms</td>
          </tr>
          <tr>
            <td>메모리 한도</td>
            <td>128MB</td>
            <td>256MB</td>
          </tr>
        </tbody>
      </table>

      <h2>함수 만들기</h2>
      <p>
        <code>/serverless</code> 페이지에서 <strong>새 함수 만들기</strong> 버튼을 클릭하거나 <code>/serverless/new</code>로 직접 접속합니다.
        이름, 런타임(JavaScript / TypeScript), 설명을 입력한 뒤 코드를 작성합니다.
      </p>
      <blockquote>
        <p>함수 이름은 계정 내에서 <strong>고유</strong>해야 합니다. 중복된 이름은 등록할 수 없습니다.</p>
      </blockquote>

      <h2>핸들러 작성 방법</h2>
      <p>
        함수는 반드시 <code>handler</code>라는 이름의 기본 내보내기(default export) 함수로 작성해야 합니다.
        함수는 <code>request</code> 객체를 인자로 받고, <code>Response</code>를 반환해야 합니다.
      </p>

      <h3>기본 형태</h3>
      <pre><code>{`export default async function handler(request) {
  return new Response("Hello, World!", { status: 200 });
}`}</code></pre>

      <h3>request 객체</h3>
      <table>
        <thead>
          <tr>
            <th>속성</th>
            <th>타입</th>
            <th>설명</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>method</code></td>
            <td><code>string</code></td>
            <td>HTTP 메서드 (GET, POST 등)</td>
          </tr>
          <tr>
            <td><code>url</code></td>
            <td><code>string</code></td>
            <td>요청 URL</td>
          </tr>
          <tr>
            <td><code>headers</code></td>
            <td><code>Record&lt;string, string&gt;</code></td>
            <td>요청 헤더</td>
          </tr>
          <tr>
            <td><code>body</code></td>
            <td><code>string | null</code></td>
            <td>요청 본문 (raw string)</td>
          </tr>
          <tr>
            <td><code>json()</code></td>
            <td><code>() =&gt; object</code></td>
            <td>본문을 JSON으로 파싱</td>
          </tr>
          <tr>
            <td><code>text()</code></td>
            <td><code>() =&gt; string</code></td>
            <td>본문을 문자열로 반환</td>
          </tr>
        </tbody>
      </table>

      <h3>Response 생성자</h3>
      <pre><code>{`new Response(body, { status, headers })`}</code></pre>
      <ul>
        <li><code>body</code> — 응답 본문 (string)</li>
        <li><code>status</code> — HTTP 상태 코드 (기본값: 200)</li>
        <li><code>headers</code> — 응답 헤더 객체</li>
      </ul>

      <h3>예시 — JSON API</h3>
      <pre><code>{`export default async function handler(request) {
  const body = request.json();
  const name = body.name ?? "World";

  return new Response(JSON.stringify({ message: \`Hello, \${name}!\` }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}`}</code></pre>

      <h2>샌드박스 내 사용 가능한 API</h2>
      <p>함수 실행 환경에는 다음 API만 제공됩니다. Node.js 기본 모듈(<code>fs</code>, <code>path</code> 등)은 사용할 수 없습니다.</p>
      <table>
        <thead>
          <tr>
            <th>API</th>
            <th>설명</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>console.log / warn / error</code></td>
            <td>실행 로그에 기록됩니다.</td>
          </tr>
          <tr>
            <td><code>fetch(url, options?)</code></td>
            <td>외부 HTTP 요청. 사설 IP 대역은 차단됩니다.</td>
          </tr>
          <tr>
            <td><code>env</code></td>
            <td>환경변수 탭에서 등록한 키-값 객체</td>
          </tr>
          <tr>
            <td><code>Response</code></td>
            <td>응답 객체 생성자</td>
          </tr>
        </tbody>
      </table>

      <h3>환경변수 사용</h3>
      <pre><code>{`export default async function handler(request) {
  const apiKey = env.API_KEY; // 환경변수 탭에서 등록한 값
  // ...
}`}</code></pre>
      <blockquote>
        <p>환경변수는 함수 상세 페이지 <strong>환경변수 탭</strong>에서 등록·수정할 수 있습니다.</p>
      </blockquote>

      <h2>보안 — fetch 제한</h2>
      <p>
        샌드박스 내 <code>fetch</code>는 외부 공개 IP로만 요청이 가능합니다.
        다음 대역은 SSRF 방어를 위해 차단됩니다.
      </p>
      <ul>
        <li><code>127.x.x.x</code> (루프백)</li>
        <li><code>10.x.x.x</code>, <code>172.16–31.x.x</code>, <code>192.168.x.x</code> (사설망)</li>
        <li><code>169.254.x.x</code> (링크 로컬), <code>100.64–127.x.x</code> (공유 주소)</li>
        <li>IPv6 루프백 / 사설 대역</li>
      </ul>
      <blockquote>
        <p>내부 서비스(DB, 메타데이터 서버 등)에 대한 요청은 도메인 기반 DNS 리바인딩을 포함하여 모두 차단됩니다.</p>
      </blockquote>

      <h2>트리거</h2>
      <p>함수 상세 페이지의 <strong>트리거 탭</strong>에서 트리거를 추가할 수 있습니다. 트리거는 두 종류를 지원합니다.</p>

      <h3>HTTP 트리거</h3>
      <p>
        HTTP 트리거를 활성화하면 아래 URL로 함수를 외부에서 호출할 수 있습니다.
      </p>
      <pre><code>{`https://fn.gsmsv.site/{userId}/{funcName}`}</code></pre>
      <ul>
        <li><code>userId</code> — 계정 ID (함수 상세 페이지에서 확인 가능)</li>
        <li><code>funcName</code> — 함수 이름</li>
      </ul>
      <p>
        HTTP 메서드를 <strong>ANY</strong>로 설정하면 GET, POST 등 모든 메서드를 허용합니다.
        특정 메서드만 받으려면 GET / POST / PUT / DELETE 중 하나를 선택합니다.
      </p>
      <blockquote>
        <p>HTTP 트리거 URL은 인증 없이 공개됩니다. 민감한 작업에는 <code>env</code>로 API Key를 관리하고 핸들러에서 직접 검증하세요.</p>
      </blockquote>

      <h3>크론 트리거</h3>
      <p>
        크론 표현식을 등록하면 지정한 스케줄에 따라 함수가 자동으로 실행됩니다.
      </p>
      <table>
        <thead>
          <tr>
            <th>예시 표현식</th>
            <th>실행 주기</th>
          </tr>
        </thead>
        <tbody>
          <tr><td><code>* * * * *</code></td><td>매 1분</td></tr>
          <tr><td><code>0 * * * *</code></td><td>매 시 정각</td></tr>
          <tr><td><code>0 9 * * 1-5</code></td><td>평일 오전 9시</td></tr>
          <tr><td><code>0 0 * * *</code></td><td>매일 자정</td></tr>
        </tbody>
      </table>
      <blockquote>
        <p>크론 표현식은 5자리 표준 POSIX cron 형식을 사용합니다 (분 시 일 월 요일).</p>
      </blockquote>

      <h2>실행 로그</h2>
      <p>
        함수 상세 페이지의 <strong>로그 탭</strong>에서 최근 실행 기록을 확인할 수 있습니다.
        각 로그 항목에는 실행 트리거 유형, 상태(success / error / timeout), 실행 시간(ms), <code>console</code> 출력이 포함됩니다.
      </p>

      <h2>테스트 실행</h2>
      <p>
        함수 상세 페이지의 <strong>테스트 탭</strong>에서 트리거 없이 함수를 즉시 실행할 수 있습니다.
        요청 본문(JSON)을 직접 입력하고 응답과 로그를 실시간으로 확인합니다.
      </p>
    </DocsLayout>
  )
}
