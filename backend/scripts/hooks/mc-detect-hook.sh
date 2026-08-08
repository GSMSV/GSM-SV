#!/bin/bash
set -uo pipefail

# hookscript
VMID="$1" # VMID: Proxmox가 넘긴 대상 VM 번호
PHASE="$2" # PHASE: 생애주기 단계
MAX_RETRIES=10 # MAX_RETRIES: for문 횟수 상수
SLEEP_SEC=5 # SLEEP_SEC: for문 대기 시간 상수


if [ -z "$PHASE" ]; then
    echo "proxmox가 수집한 단계 정보가 없습니다."
    exit 0
fi

if [ "$PHASE" = "post-start" ]; then
    WEBHOOK_URL=$(cat /etc/mc-detect/webhook 2>/dev/null)
    message="$VMID 에서 마인크래프트 서버가 발견되었습니다"

    if [ -z "$WEBHOOK_URL" ]; then
        echo "WEBHOOK URL이 NULL 이거나 문자열의 길이가 0 입니다."
        exit 0
    fi
    echo "post-start 상태"

    # guest-agent가 post-start 직후 아직 안 떴을 수 있어 최대 10회 재시도
    success=false

    for((i=1; i<=$MAX_RETRIES; i++)); do
        if qm guest cmd "$VMID" ping; then
            # ping 성공, agent 응답 가능 상태
            
            result=$(qm guest exec "$VMID" -- sh -c '
                paths=""
                for dir in /home /opt /srv /root; do # vm에 folder 있는지 확인
                    if [ -d "$dir" ]; then
                        paths="$paths $dir"
                    fi
                done

                if [ -n "$paths" ]; then
                        find $paths -name "server.properties" -type f
                    else
                        echo "검사 할 폴더가 없습니다." >&2 # stderr로 전송
                        exit 0
                fi
                ')
            
            exitcode=$(echo "$result" | jq -r '.exitcode') # exitcode 검사 후 0 이면, path 검사 진행하는 로직

            if [ "$exitcode" != "0" ]; then # -ne 0는 result가 비정상 json일 때 interger expression ecpected error 발생
                echo "검사 실패 (exitcode: $exitcode)"
                exit 0 # proxmox 기준 검사는 실패했지만, vm은 동작하기 때문에 exitcode는 0
            fi

            path=$(echo "$result" | jq -r '.["out-data"] // ""') # jq Null check

            if [ -n "$path" ]; then
                payload=$(jq -n --arg content "$message" '{content: $content}')
                if curl --max-time 5 --fail -s -o /dev/null -H "Content-Type: application/json" -d "$payload" "$WEBHOOK_URL"; then
                    echo "성공"
                else
                    echo "실패"
                fi
            fi

            # agent 응답 + 검사 완료(발견 여부 무관) 시점에 loop 탈출
            success=true
            break
        fi
        sleep "$SLEEP_SEC" # agent 부팅 대기 후 다음 시도
    done

    if [ "$success" = false ]; then
        echo "agent 부팅 실패"
        exit 0 # proxmox 기준 검사는 실패했지만, vm은 동작하기 때문에 exitcode는 0
    fi 
fi
