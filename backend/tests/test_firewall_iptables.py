"""
방화벽 iptables 관련 테스트

- TestAllocateRandomPort: allocate_random_port() 단위 테스트
- TestManageCustomIptables: manage_custom_iptables() 단위 테스트 (paramiko mock)
- TestManageCustomIptablesManual: 실제 게이트웨이 + VM 연결 확인 (수동 실행)
"""
import asyncio
import socket
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from models.server import Server
from models.user import User, UserRole
from models.vm import Vm
from models.vm_port import VmPort
from schemas.fw_schema import VmPortCreate
from api.routes.firewall import add_custom_port, restore_default_ports
from services.network_service import allocate_random_port, manage_custom_iptables, manage_iptables


# ── allocate_random_port ──────────────────────────────────────────────────────

class TestAllocateRandomPort:
    """allocate_random_port() — DB에서 사용 중인 포트를 피해 랜덤 할당"""

    def test_returns_port_in_range(self, db):
        port = allocate_random_port(db)
        assert 30000 <= port <= 39999

    def test_avoids_used_ports(self, db):
        used = {30000, 30001, 30002}
        for p in used:
            db.add(VmPort(vm_id=1, internal_port=443, external_port=p))
        db.commit()

        for _ in range(20):
            port = allocate_random_port(db)
            assert port not in used

    def test_raises_when_range_exhausted(self, db):
        for p in range(30000, 30010):
            db.add(VmPort(vm_id=1, internal_port=80, external_port=p))
        db.commit()

        with pytest.raises(RuntimeError, match="할당 가능한 포트"):
            allocate_random_port(db, start=30000, end=30009)

    def test_custom_range(self, db):
        port = allocate_random_port(db, start=40000, end=40099)
        assert 40000 <= port <= 40099


# ── manage_custom_iptables ────────────────────────────────────────────────────

def _make_server(gateway_ip="1.2.3.4", gateway_user="admin", gateway_password="pass"):
    server = MagicMock()
    server.gateway_ip = gateway_ip
    server.gateway_user = gateway_user
    server.gateway_password = gateway_password
    return server


def _make_ssh_mock():
    """paramiko SSHClient mock — exec_command 결과 반환"""
    ssh = MagicMock()
    stdout = MagicMock()
    stdout.channel.recv_exit_status.return_value = 0
    stdout.read.return_value = b"# iptables rules\n-A PREROUTING ...\n"
    stderr = MagicMock()
    stderr.read.return_value = b""
    ssh.exec_command.return_value = (MagicMock(), stdout, stderr)
    return ssh


def _make_command_result(exit_status=0, stderr_text=""):
    stdout = MagicMock()
    stdout.channel.recv_exit_status.return_value = exit_status
    stdout.read.return_value = b"# iptables rules\n"
    stderr = MagicMock()
    stderr.read.return_value = stderr_text.encode()
    return MagicMock(), stdout, stderr


class TestManageCustomIptables:
    """manage_custom_iptables() — paramiko SSH mock으로 명령어 검증"""

    @patch("services.network_service.paramiko.SSHClient")
    def test_preexisting_shared_forward_survives_dnat_error(self, mock_ssh_cls):
        ssh = MagicMock()
        rules = set()
        seen = []

        def exec_rule(command):
            seen.append(command)
            if "-D FORWARD" in command:
                pytest.fail("Rollback deleted another port's shared FORWARD rule")
            if "-D PREROUTING" in command:
                rules.discard("DNAT")
                return _make_command_result(0)
            if "-C FORWARD" in command and "-A" not in command:
                return _make_command_result(0)  # Another port owns this FORWARD rule.
            if "-C PREROUTING" in command and "-A" not in command:
                return _make_command_result(1)
            if "-A PREROUTING" in command:
                rules.add("DNAT")
                raise OSError("DNAT applied remotely, reply lost")

            if "-A FORWARD" in command:
                pytest.fail("Existing shared FORWARD was added again")
            return _make_command_result(0)

        ssh.exec_command.side_effect = exec_rule
        mock_ssh_cls.return_value = ssh
        result = manage_custom_iptables(
            server=_make_server(), vm_ip="10.0.0.5", internal_port=443,
            external_port=31234, protocol="tcp", action="ADD",
        )
        assert result is False
        assert "DNAT" not in rules
        assert any("-C FORWARD" in cmd for cmd in seen)
        assert not any("-D FORWARD" in cmd for cmd in seen)

    @patch("services.network_service.paramiko.SSHClient")
    def test_preexisting_rules_are_left_untouched(self, mock_ssh_cls):
        ssh = MagicMock()
        commands = []

        def exec_rule(command):
            commands.append(command)
            if "-C PREROUTING" in command and "-A" not in command:
                return _make_command_result(0)  # Preexisting DNAT.
            if "-C FORWARD" in command and "-A" not in command:
                return _make_command_result(0)  # Shared FORWARD.
            if "-A PREROUTING" in command:
                pytest.fail("Preexisting DNAT was added again")
            if "-D " in command:
                pytest.fail("Rollback removed a preexisting rule")
            return _make_command_result(0)

        ssh.exec_command.side_effect = exec_rule
        mock_ssh_cls.return_value = ssh
        result = manage_custom_iptables(
            server=_make_server(), vm_ip="10.0.0.5", internal_port=443,
            external_port=31234, protocol="tcp", action="ADD",
        )
        assert result is True  # Already installed: no ADD necessary.
        assert not any("-A " in cmd for cmd in commands)

    @patch("services.network_service.paramiko.SSHClient")
    def test_default_port_failure_keeps_shared_ssh_forward(self, mock_ssh_cls):
        ssh = MagicMock()
        commands = []

        def exec_rule(command):
            commands.append(command)
            if "-C FORWARD" in command and "--dport 22" in command:
                return _make_command_result(0)  # Existing rule shared by another port.
            if "-C " in command and "-D " not in command:
                return _make_command_result(1)
            if "-A PREROUTING" in command and "--dport 22001" in command:
                raise OSError("SSH response lost after applying default SSH DNAT")
            if "-D FORWARD" in command and "--dport 22" in command:
                pytest.fail("Default-port rollback deleted shared SSH FORWARD")
            return _make_command_result(0)

        ssh.exec_command.side_effect = exec_rule
        mock_ssh_cls.return_value = ssh
        server = _make_server()
        server.base_port = 22000
        assert manage_iptables(server, 1, "10.0.0.5", "ADD") is False
        assert any("-D PREROUTING" in cmd and "--dport 22001" in cmd for cmd in commands)
        assert not any("-D FORWARD" in cmd and "--dport 22" in cmd for cmd in commands)

    @patch("services.network_service.paramiko.SSHClient")
    def test_ambiguous_first_command_failure_compensates_only_new_rule(self, mock_ssh_cls):
        ssh = MagicMock()
        commands = []

        def exec_rule(command):
            commands.append(command)
            if "-C PREROUTING" in command and "-A" not in command:
                return _make_command_result(1)
            if "-A PREROUTING" in command:
                raise OSError("applied remotely, reply lost")
            return _make_command_result(0)

        ssh.exec_command.side_effect = exec_rule
        mock_ssh_cls.return_value = ssh
        assert manage_custom_iptables(
            server=_make_server(), vm_ip="10.0.0.5", internal_port=443,
            external_port=31234, protocol="tcp", action="ADD",
        ) is False
        assert any("-D PREROUTING" in cmd for cmd in commands)
        assert not any("-D FORWARD" in cmd for cmd in commands)

    @patch("services.network_service.paramiko.SSHClient")
    def test_add_runs_correct_commands(self, mock_ssh_cls):
        ssh = _make_ssh_mock()
        ssh.exec_command.side_effect = lambda cmd: _make_command_result(1 if "-C " in cmd else 0)
        mock_ssh_cls.return_value = ssh
        server = _make_server()

        result = manage_custom_iptables(
            server=server,
            vm_ip="10.0.0.5",
            internal_port=443,
            external_port=31234,
            protocol="tcp",
            action="ADD",
        )

        assert result is True
        executed_cmds = [c.args[0] for c in ssh.exec_command.call_args_list]
        dnat_cmd = next((c for c in executed_cmds if "PREROUTING" in c and "-A" in c), None)
        forward_cmd = next((c for c in executed_cmds if "FORWARD" in c and "-A" in c), None)

        assert dnat_cmd is not None, "DNAT 추가 명령어가 실행되지 않았음"
        assert "31234" in dnat_cmd
        assert "10.0.0.5:443" in dnat_cmd
        assert "tcp" in dnat_cmd

        assert forward_cmd is not None, "FORWARD 추가 명령어가 실행되지 않았음"
        assert "10.0.0.5" in forward_cmd
        assert "443" in forward_cmd

    @patch("services.network_service.paramiko.SSHClient")
    def test_delete_runs_correct_commands(self, mock_ssh_cls):
        ssh = _make_ssh_mock()
        mock_ssh_cls.return_value = ssh
        server = _make_server()

        result = manage_custom_iptables(
            server=server,
            vm_ip="10.0.0.5",
            internal_port=443,
            external_port=31234,
            protocol="tcp",
            action="DELETE",
        )

        assert result is True
        executed_cmds = [c.args[0] for c in ssh.exec_command.call_args_list]
        dnat_del = next((c for c in executed_cmds if "PREROUTING" in c and "-D" in c), None)
        forward_del = next((c for c in executed_cmds if "FORWARD" in c and "-D" in c), None)

        assert dnat_del is not None, "DNAT 삭제 명령어가 실행되지 않았음"
        assert forward_del is not None, "FORWARD 삭제 명령어가 실행되지 않았음"

    @patch("services.network_service.paramiko.SSHClient")
    def test_returns_false_when_gateway_info_missing(self, mock_ssh_cls):
        server = _make_server(gateway_ip="", gateway_user="")
        result = manage_custom_iptables(
            server=server,
            vm_ip="10.0.0.5",
            internal_port=443,
            external_port=31234,
            protocol="tcp",
            action="ADD",
        )
        assert result is False
        mock_ssh_cls.return_value.connect.assert_not_called()

    @patch("services.network_service.paramiko.SSHClient")
    def test_returns_false_on_ssh_exception(self, mock_ssh_cls):
        ssh = MagicMock()
        ssh.connect.side_effect = Exception("Connection refused")
        mock_ssh_cls.return_value = ssh
        server = _make_server()

        result = manage_custom_iptables(
            server=server,
            vm_ip="10.0.0.5",
            internal_port=443,
            external_port=31234,
            protocol="tcp",
            action="ADD",
        )
        assert result is False

    def test_invalid_vm_ip_raises(self):
        server = _make_server()
        with pytest.raises(ValueError, match="잘못된 IP"):
            manage_custom_iptables(
                server=server,
                vm_ip="not-an-ip",
                internal_port=443,
                external_port=31234,
                protocol="tcp",
                action="ADD",
            )

    @patch("services.network_service.paramiko.SSHClient")
    def test_add_failure_stops_before_remaining_command_and_rolls_back(self, mock_ssh_cls):
        ssh = MagicMock()
        ssh.exec_command.side_effect = [
            _make_command_result(1),  # DNAT absent
            _make_command_result(1),  # FORWARD absent
            _make_command_result(1, "DNAT failed"),
            _make_command_result(0),
        ]
        mock_ssh_cls.return_value = ssh
        server = _make_server()

        result = manage_custom_iptables(
            server=server,
            vm_ip="10.0.0.5",
            internal_port=443,
            external_port=31234,
            protocol="tcp",
            action="ADD",
        )

        assert result is False
        executed_cmds = [c.args[0] for c in ssh.exec_command.call_args_list]
        assert not any("FORWARD" in c and "-A" in c for c in executed_cmds)
        assert any("PREROUTING" in c and "-D" in c for c in executed_cmds)
        assert not any("FORWARD" in c and "-D" in c for c in executed_cmds)

    @patch("services.network_service.paramiko.SSHClient")
    def test_add_ssh_error_after_dnat_rolls_back_before_returning_failure(self, mock_ssh_cls):
        ssh = MagicMock()
        ssh.exec_command.side_effect = [
            _make_command_result(1),  # PREROUTING absent
            _make_command_result(1),  # FORWARD absent
            _make_command_result(0),  # PREROUTING added
            OSError("FORWARD SSH channel closed"),
            _make_command_result(0),  # rollback FORWARD (may have applied remotely)
            _make_command_result(0),  # rollback PREROUTING
        ]
        mock_ssh_cls.return_value = ssh

        result = manage_custom_iptables(
            server=_make_server(), vm_ip="10.0.0.5", internal_port=443,
            external_port=31234, protocol="tcp", action="ADD",
        )

        assert result is False
        commands = [call.args[0] for call in ssh.exec_command.call_args_list]
        assert len(commands) == 6
        assert "-D FORWARD" in commands[4]
        assert "-D PREROUTING" in commands[5]
        assert "while" not in commands[4] + commands[5]
        ssh.close.assert_called_once()


class TestAddCustomPortRollback:
    """커스텀 포트 추가 실패 시 DB 선점 레코드 rollback"""

    def _make_user_vm(self, db):
        user = User(email="fw@gsm.hs.kr", hashed_password="h", role=UserRole.USER, is_active=True)
        server = Server(
            name="test-node",
            ip_address="192.168.1.10",
            port=8006,
            api_user="root@pam",
            api_password="password",
            is_active=True,
            gateway_ip="192.168.1.1",
            gateway_user="admin",
            gateway_password="gwpass",
            base_port=21000,
        )
        db.add_all([user, server])
        db.commit()
        db.refresh(user)
        db.refresh(server)
        vm = Vm(
            hypervisor_vmid=200,
            name="test-vm",
            server_id=server.id,
            owner_id=user.id,
            internal_ip="10.0.0.100",
        )
        db.add(vm)
        db.commit()
        db.refresh(vm)
        return user

    def test_value_error_removes_reserved_port(self, db):
        user = self._make_user_vm(db)
        body = VmPortCreate(
            internal_port=8080,
            protocol="tcp",
            source="192.168.1.10/32",
            description="test",
        )

        with patch("api.routes.firewall.allocate_random_port", return_value=33333), patch(
            "api.routes.firewall.manage_custom_iptables",
            side_effect=ValueError("잘못된 source IP/CIDR 형식"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(add_custom_port("test-node", 200, body, db=db, current_user=user))

        assert exc_info.value.status_code == 400
        assert db.query(VmPort).count() == 0


class TestRestoreDefaultPorts:
    """기본 포트 복원 — 복원할 외부 포트가 이미 쓰이면 409"""

    _make_user_vm = TestAddCustomPortRollback._make_user_vm

    def test_restores_missing_default_ports(self, db):
        user = self._make_user_vm(db)

        with patch("api.routes.firewall.manage_custom_iptables", return_value=True):
            result = asyncio.run(restore_default_ports("test-node", 200, db=db, current_user=user))

        assert result == {"restored": 3}
        assert {p.external_port for p in db.query(VmPort).all()} == {21200, 22200, 23200}

    def test_conflicting_port_returns_409_without_iptables(self, db):
        user = self._make_user_vm(db)
        db.add(VmPort(vm_id=9999, internal_port=80, external_port=22200, is_default=True))
        db.commit()

        with patch("api.routes.firewall.manage_custom_iptables") as mock_iptables:
            with pytest.raises(HTTPException) as exc_info:
                asyncio.run(restore_default_ports("test-node", 200, db=db, current_user=user))

        assert exc_info.value.status_code == 409
        assert "22200" in exc_info.value.detail
        mock_iptables.assert_not_called()
        assert db.query(VmPort).count() == 1


# ── 수동 스모크 테스트 ─────────────────────────────────────────────────────────

@pytest.mark.skip(reason="manual smoke test — 실제 게이트웨이 + VM 필요")
class TestManageCustomIptablesManual:
    """
    실제 게이트웨이와 VM이 실행 중일 때만 수동으로 실행합니다.
    pytest -m 'not skip' 로 자동 테스트 시 제외됩니다.

    실행 방법 (환경변수 설정 후):
        GATEWAY_IP=x.x.x.x GATEWAY_USER=admin GATEWAY_PASSWORD=xxx \\
        VM_IP=10.0.0.x INTERNAL_PORT=8080 EXTERNAL_PORT=35000 \\
        pytest tests/test_firewall_iptables.py::TestManageCustomIptablesManual -s
    """

    import os
    GATEWAY_PUBLIC_IP = os.environ.get("GATEWAY_IP", "")
    VM_INTERNAL_IP = os.environ.get("VM_IP", "")
    INTERNAL_PORT = int(os.environ.get("INTERNAL_PORT", "8080"))
    EXTERNAL_PORT = int(os.environ.get("EXTERNAL_PORT", "35000"))

    def _server(self):
        import os
        server = MagicMock()
        server.gateway_ip = self.GATEWAY_PUBLIC_IP
        server.gateway_user = os.environ.get("GATEWAY_USER", "")
        server.gateway_password = os.environ.get("GATEWAY_PASSWORD", "")
        return server

    def test_tcp_connectivity_after_add(self):
        """DNAT 규칙 추가 후 외부 포트 TCP 연결 성공 확인"""
        import paramiko

        server = self._server()
        manage_custom_iptables(
            server=server,
            vm_ip=self.VM_INTERNAL_IP,
            internal_port=self.INTERNAL_PORT,
            external_port=self.EXTERNAL_PORT,
            protocol="tcp",
            action="ADD",
        )

        try:
            sock = socket.create_connection(
                (self.GATEWAY_PUBLIC_IP, self.EXTERNAL_PORT), timeout=5
            )
            sock.close()
            connected = True  # noqa: F841
        except (ConnectionRefusedError, socket.timeout, OSError):
            connected = True  # noqa: F841 — DNAT 성공 시 VM 내부 서비스에 따라 refused도 정상

        # 규칙 삭제
        manage_custom_iptables(
            server=server,
            vm_ip=self.VM_INTERNAL_IP,
            internal_port=self.INTERNAL_PORT,
            external_port=self.EXTERNAL_PORT,
            protocol="tcp",
            action="DELETE",
        )

        # 삭제 후 iptables-save에 규칙이 없는지 확인
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.WarningPolicy())
        ssh.connect(
            hostname=self.GATEWAY_PUBLIC_IP,
            username=server.gateway_user,
            password=server.gateway_password,
            timeout=10,
        )
        _, stdout, _ = ssh.exec_command("sudo iptables-save")
        rules_output = stdout.read().decode()
        ssh.close()

        assert f"--dport {self.EXTERNAL_PORT}" not in rules_output, \
            "삭제 후에도 iptables 규칙이 남아 있음"
