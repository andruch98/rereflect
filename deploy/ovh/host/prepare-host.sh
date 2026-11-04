#!/usr/bin/env bash
# Run only on the newly purchased Ubuntu VPS, through an already tested SSH key.
set -euo pipefail
umask 077
fail() { printf '%s\n' "$*" >&2; exit 1; }
[[ $EUID -eq 0 ]] || fail 'Run with sudo on the new VPS.'
[[ $# -eq 2 && $2 == --key-login-confirmed ]] || fail 'Usage: sudo bash prepare-host.sh OPERATOR --key-login-confirmed (test a second key-only SSH login first).'
operator=$1
[[ $operator =~ ^[a-z_][a-z0-9_-]*$ && $operator != root ]] || fail 'Use the existing non-root Ubuntu operator.'
source /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 ]] || fail 'This bootstrap is scoped to a fresh Ubuntu 24.04 VPS.'
operator_home=$(getent passwd "$operator" | cut -d: -f6)
[[ -n $operator_home && -s $operator_home/.ssh/authorized_keys ]] || fail 'Install and test the operator public SSH key first.'
ssh-keygen -l -f "$operator_home/.ssh/authorized_keys" >/dev/null || fail 'No valid authorized SSH key found.'
id -nG "$operator" | tr ' ' '\n' | grep -qx sudo || fail 'Operator must already be in the sudo group.'
prepared=/etc/boomsay/host-prepared
local_docker=(env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock)
if [[ ! -e $prepared ]]; then
  if command -v docker >/dev/null; then
    containers=$("${local_docker[@]}" ps -aq) || fail 'Local Docker state cannot be inspected; inspect the host manually.'
    [[ -z $containers ]] || fail 'Existing containers found; refusing to alter an unrelated host.'
  fi
  listeners=$(ss -H -ltn '( sport = :80 or sport = :443 or sport = :5432 or sport = :6379 )') || fail 'Cannot inspect existing network listeners.'
  [[ -z $listeners ]] || fail 'Existing application/database listeners found; use a fresh VPS.'
  for package in docker.io docker-compose docker-compose-v2 podman-docker containerd runc; do
    if dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx installed; then
      fail "Conflicting package $package exists; inspect it manually instead of removing it."
    fi
  done
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl ufw fail2ban unattended-upgrades age git
install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod 0644 /etc/apt/keyrings/docker.asc
cat >/etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: noble
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
"${local_docker[@]}" compose version
install -d -m 0700 /etc/boomsay /var/backups/boomsay
install -d -m 0755 /etc/ssh/sshd_config.d /etc/systemd/journald.conf.d /etc/fail2ban/jail.d
ssh_stage=$(mktemp -d /etc/boomsay/.ssh-rollback.XXXXXXXX)
ssh_target=/etc/ssh/sshd_config.d/00-boomsay.conf
ssh_success=0
[[ ! -e $ssh_target ]] || cp -p "$ssh_target" "$ssh_stage/original"
restore_ssh_on_failure() {
  if [[ $ssh_success -eq 0 ]]; then
    if [[ -f $ssh_stage/original ]]; then cp -p "$ssh_stage/original" "$ssh_target"; else rm -f "$ssh_target"; fi
    /usr/sbin/sshd -t && systemctl reload ssh || true
  fi
  rm -rf -- "$ssh_stage"
}
trap restore_ssh_on_failure EXIT
cat >/etc/ssh/sshd_config.d/00-boomsay.conf <<EOF
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
AllowUsers $operator
EOF
/usr/sbin/sshd -t
effective=$(/usr/sbin/sshd -T -C "user=$operator,host=localhost,addr=127.0.0.1")
for expected in 'passwordauthentication no' 'kbdinteractiveauthentication no' 'permitrootlogin no' 'pubkeyauthentication yes' 'port 22'; do
  grep -qx "$expected" <<<"$effective" || fail 'SSH effective configuration conflicts; inspect before reloading.'
done
cat >/etc/fail2ban/jail.d/boomsay.conf <<'EOF'
[sshd]
enabled = true
backend = systemd
maxretry = 5
bantime = 3600
EOF
cat >/etc/apt/apt.conf.d/52boomsay-unattended <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
Unattended-Upgrade::Automatic-Reboot "false";
EOF
cat >/etc/systemd/journald.conf.d/boomsay.conf <<'EOF'
[Journal]
SystemMaxUse=200M
RuntimeMaxUse=50M
EOF
ufw default deny incoming
ufw default allow outgoing
ufw limit 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
systemctl reload ssh
systemctl restart fail2ban systemd-journald
date -u +%FT%TZ >"$prepared"
ssh_success=1
printf '%s\n' 'Host preparation completed. Keep this session open and test another key-only SSH login.' 'Only the Compose proxy may publish ports; Docker published ports bypass UFW.' 'Docker access remains through sudo; no user was added to the root-equivalent docker group.'
