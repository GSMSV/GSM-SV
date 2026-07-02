#!/bin/bash


VMID="$1" # VMID: Proxmox가 넘긴 대상 VM 번호
PHASE="$2" # PHASE: 생애주기 단계

if [ -z "$PHASE" ]; then
    echo "proxmox가 수집한 단계 정보가 없습니다."
    exit
fi

if [ "$PHASE" = "post-start" ]; then
    echo "post-start 상태"

    # guest-agent가 post-start 직후 아직 안 떴을 수 있어 최대 20회 재시도
    success=false

    for((i=1; i<=20; i++)); do
        if qm guest cmd "$VMID" ping; then
            # ping 성공, agent 응답 가능 상태

            result=$(qm guest exec "$VMID" -- sh -c '
                for dir in /home /opt /srv /root; do # vm에 folder 있는지 확인
                    if [ -d "$dir" ]; then
                        paths="$paths $dir"
                    fi
                done
                # find의 에러는 out-data가 아닌 err-data로 분리되므로 JSON 파싱에 영향 없음. 단, exitcode는 0이 아니게 되므로 없는 경로는 위 -d 검사로 미리 걸러냄
                find $paths -name "server.properties" -type f # vm에 있는 folder만 조회')

            exitcode=$(echo "$result" | jq -r '.exitcode') # exitcode 검사 후 0 이면, path 검사 진행하는 로직

            if [ "$exitcode" -ne 0 ]; then
                echo "검사 실패 (exitcode: $exitcode)"
                exit
            fi

            path=$(echo "$result" | jq -r '.["out-data"] // ""') # jq Null check

            if [ -n "$path" ]; then
                echo "발견 : '$VMID' 에 마인크래프트 서버가 발견되었습니다."
                # discord 웹훅으로 알림 기능 확장
            fi
            success=true
            break # 검사 완료 및 loop 탈출
        fi
        sleep 5 # agent 부팅 대기 후 다음 시도
    done

    if [ "$success" = false ]; then
        echo "agent 부팅 실패"
        exit
    fi

fi
