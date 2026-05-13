"use client"

import { DocsLayout } from "@/components/docs/docs-layout"

export default function GettingStartedPage() {
  return (
    <DocsLayout>
      <h1>시작하기</h1>

      <h2>GSM SV에 대하여</h2>
      <p>
        <strong>GSM SV</strong>는 광주소프트웨어마이스터고등학교 학생들의 공부와 프로젝트 배포를 돕기 위해 만들어진
        교내 IaaS(Infrastructure as a Service) 플랫폼입니다. 교내에 유휴 상태로 있는 GPU 서버 자원을 통합하여,
        학생 누구나 비용 부담 없이 가상 서버(VM)를 자유롭게 사용할 수 있습니다.
      </p>
      <p>
        웹 기반 콘솔(<strong>GSM SV Console</strong>)을 통해 VM 생성부터 전원 제어, 방화벽 설정,
        리소스 모니터링까지 모든 작업을 간편하게 수행할 수 있습니다.
      </p>

      <h2>서비스 도메인</h2>
      <p>GSM SV는 다음 도메인을 통해 제공됩니다.</p>
      <table>
        <thead>
          <tr>
            <th>도메인</th>
            <th>용도</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><code>gsmsv.site</code></td>
            <td>서비스 웹페이지 (콘솔 접속)</td>
          </tr>
          <tr>
            <td><code>ssh.gsmsv.site</code></td>
            <td>VM SSH 접속용 도메인</td>
          </tr>
          <tr>
            <td><code>service.gsmsv.site</code></td>
            <td>VM 웹 서비스(HTTP/SVC) 접속용 도메인</td>
          </tr>
        </tbody>
      </table>

      <h2>⚠️ 이용 시 주의사항</h2>
      <ul>
        <li>인스턴스 배포 시 제공되는 초기 비밀번호를 계속 사용하는 것은 권장하지 않습니다. 본인만 알 수 있는 비밀번호로 변경하거나 SSH Key를 설정하는 것을 추천드립니다.</li>
        <li>일반 사용자(USER)의 VM은 생성 후 <strong>30일이 지나면 자동 삭제</strong>됩니다. 중요한 데이터는 GitHub 등 외부 저장소에 미리 백업해 주세요.</li>
        <li>GSM SV는 교내 공유 자원입니다. 채굴, 게임(특정 상황 제외) 등 <strong>교육 목적에 맞지 않는 용도</strong>로 사용할 경우 사전 안내 없이 인스턴스가 삭제될 수 있습니다.</li>
        <li>본인의 부주의로 인하여 발생한 피해는 GSM SV에서 책임을 지지 않습니다.</li>
      </ul>

      <h2>제공 기능</h2>
      <ul>
        <li><strong>VM 프로비저닝</strong> — 웹 콘솔에서 클릭 몇 번으로 Ubuntu 22.04 LTS 기반 VM을 생성할 수 있습니다.</li>
        <li><strong>전원 제어</strong> — 시작, 종료, 강제종료, 재시작을 웹에서 직접 제어합니다.</li>
        <li><strong>포트포워딩</strong> — VM 생성 시 SSH, HTTP, SVC 포트가 자동으로 할당됩니다.</li>
        <li><strong>방화벽 관리</strong> — Proxmox VM 레벨의 방화벽 규칙을 추가하거나 삭제할 수 있습니다.</li>
        <li><strong>리소스 모니터링</strong> — CPU, RAM 실시간 그래프(1h / 6h / 24h)로 VM 상태를 확인할 수 있습니다.</li>
        <li><strong>알림</strong> — VM 생성/삭제 및 리소스 경고(90% 초과)를 알림으로 받을 수 있습니다.</li>
        <li><strong>Serverless 함수</strong> — JavaScript / TypeScript 코드를 서버 없이 실행하고 HTTP 또는 크론으로 트리거할 수 있습니다.</li>
      </ul>

      <h2>계정 유형</h2>
      <p>GSM SV는 두 가지 계정 유형을 제공합니다.</p>
      <table>
        <thead>
          <tr>
            <th>역할</th>
            <th>설명</th>
            <th>VM 한도</th>
            <th>만료</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>USER</strong></td>
            <td>재학생 일반 계정</td>
            <td>최대 3개</td>
            <td>생성 후 30일</td>
          </tr>
          <tr>
            <td><strong>PROJECT_OWNER</strong></td>
            <td>교내 프로젝트 참여자 계정</td>
            <td>무제한</td>
            <td>없음</td>
          </tr>
        </tbody>
      </table>
      <blockquote>
        <p><strong>가입 조건:</strong> DataGSM에 등록된 GSM 재학생만 가입할 수 있습니다. 비재학생은 가입이 불가합니다.</p>
      </blockquote>

      <h2>프로젝트 오너란?</h2>
      <p>
        <strong>프로젝트 오너(PROJECT_OWNER)</strong>는 교내 프로젝트에 참여하는 학생을 위한 계정 유형입니다.
        일반 사용자보다 더 많은 리소스와 권한을 제공하며, 장기 프로젝트 운영에 적합합니다.
      </p>

      <h3>일반 사용자와의 차이점</h3>
      <table>
        <thead>
          <tr>
            <th>기능</th>
            <th>일반 사용자(USER)</th>
            <th>프로젝트 오너(PO)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>VM 생성 한도</td>
            <td>최대 3개</td>
            <td>무제한</td>
          </tr>
          <tr>
            <td>VM 만료</td>
            <td>30일</td>
            <td>없음</td>
          </tr>
          <tr>
            <td>사양 선택</td>
            <td>정해진 티어</td>
            <td>커스텀 사양</td>
          </tr>
          <tr>
            <td>핫플러그 리사이징</td>
            <td>불가</td>
            <td>가능</td>
          </tr>
          <tr>
            <td>전용 노드 배정</td>
            <td>일반 노드</td>
            <td>GPU 3 노드 전용</td>
          </tr>
        </tbody>
      </table>

      <h3>프로젝트 오너 가입 방법</h3>
      <p>프로젝트 오너 계정은 일반 가입과 별도의 절차를 통해 신청합니다.</p>
      <ol>
        <li><code>/signup/project</code> 페이지에 접속합니다.</li>
        <li>DataGSM에서 프로젝트 참여 여부를 확인합니다.</li>
        <li>참여 중인 프로젝트를 선택합니다.</li>
        <li>비밀번호와 사용 사유를 입력합니다.</li>
        <li>이메일 인증을 완료합니다.</li>
        <li><strong>관리자 승인</strong>을 기다립니다.</li>
      </ol>
      <blockquote>
        <p>관리자 승인 전까지 계정이 비활성 상태로 유지됩니다. 승인 결과는 알림으로 전달됩니다.</p>
      </blockquote>
      <blockquote>
        <p>프로젝트당 오너 계정은 <strong>1명</strong>으로 제한됩니다.</p>
      </blockquote>

      <h3>핫플러그 리사이징</h3>
      <p>
        프로젝트 오너는 VM을 재시작하지 않고도 CPU와 메모리를 실시간으로 변경할 수 있습니다.
      </p>
      <ul>
        <li><strong>CPU</strong>: 2 ~ 8소켓 범위에서 변경 가능</li>
        <li><strong>RAM</strong>: 2GB ~ 32GB 프리셋 슬라이더로 변경 가능</li>
      </ul>
      <p>
        인스턴스 상세 페이지 → <strong>설정 탭</strong>에서 변경할 수 있습니다.
      </p>
    </DocsLayout>
  )
}
