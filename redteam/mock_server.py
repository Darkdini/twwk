#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────
#  TWWK red-team · УЧЕБНЫЙ мок-сервер (две версии: наивная и защищённая)
#
#  Нужен, чтобы ты ВЖИВУЮ увидел разницу: один и тот же арсенал «врага»
#  против сервера, который доверяет клиенту, выносит игру в ноль; против
#  сервера, который всё проверяет сам, — отскакивает.
#
#  Это упрощённая модель класса уязвимости (не точный протокол TWWK):
#  кадр = [opcode:1][len:2 BE][payload]. Ответ = [0x80][len:2][payload].
#
#  Запуск:
#    наивный   : python3 mock_server.py --mode naive   --port 9933
#    защищённый: python3 mock_server.py --mode hardened --port 9934
# ─────────────────────────────────────────────────────────────────────
import socket, struct, threading, argparse, hashlib, hmac, time

OP_LOGIN   = 0x01
OP_BUILD   = 0x10
OP_SETRES  = 0x20   # «клиент сам выставляет ресурсы» — порочный дизайн
OP_GETSTATE= 0x30
OP_RESP    = 0x80

SECRET = b"server-side-only-key"   # в защищённом режиме клиент его не знает


def recv_frame(sock):
    hdr = recvn(sock, 3)
    if not hdr: return None
    op = hdr[0]
    ln = struct.unpack(">H", hdr[1:3])[0]
    payload = recvn(sock, ln) if ln else b""
    return op, payload

def recvn(sock, n):
    buf = b""
    while len(buf) < n:
        c = sock.recv(n - len(buf))
        if not c: return None
        buf += c
    return buf

def send_resp(sock, payload):
    sock.sendall(bytes([OP_RESP]) + struct.pack(">H", len(payload)) + payload)


class Player:
    def __init__(self):
        self.gold = 100
        self.buildings = 0
        self.seq = 0          # ожидаемый номер команды (анти-replay, hardened)
        self.name = "?"


def handle(sock, mode):
    p = Player()
    seen_macs = set()
    while True:
        f = recv_frame(sock)
        if f is None: break
        op, payload = f

        if op == OP_LOGIN:
            p.name = payload.decode("utf-8", "replace")[:20]
            send_resp(sock, f"OK login {p.name} gold={p.gold}".encode())

        elif op == OP_SETRES:
            amount = struct.unpack(">i", payload[:4])[0] if len(payload) >= 4 else 0
            if mode == "naive":
                # ❌ доверяем клиенту: ставим ресурсы как он сказал
                p.gold = amount
                send_resp(sock, f"OK gold={p.gold}".encode())
            else:
                # ✅ сервер — источник правды: команды «выставить ресурсы» не существует
                send_resp(sock, b"ERR forbidden: server is authoritative")

        elif op == OP_BUILD:
            if mode == "naive":
                # ❌ ни анти-replay, ни нормальной проверки
                p.gold -= 50
                p.buildings += 1
                send_resp(sock, f"OK built #{p.buildings} gold={p.gold}".encode())
            else:
                # ✅ проверки: номер команды (анти-replay) + MAC + хватает ли золота
                if len(payload) < 8 + 32:
                    send_resp(sock, b"ERR bad frame"); continue
                seq = struct.unpack(">i", payload[0:4])[0]
                mac = payload[8:8+32]
                body = payload[0:8]
                good = hmac.new(SECRET, body, hashlib.sha256).digest()
                if not hmac.compare_digest(mac, good):
                    send_resp(sock, b"ERR bad MAC (forged/tampered)"); continue
                if mac in seen_macs or seq != p.seq + 1:
                    send_resp(sock, b"ERR replay/out-of-order rejected"); continue
                if p.gold < 50:
                    send_resp(sock, b"ERR not enough gold"); continue
                seen_macs.add(mac); p.seq = seq
                p.gold -= 50; p.buildings += 1
                send_resp(sock, f"OK built #{p.buildings} gold={p.gold}".encode())

        elif op == OP_GETSTATE:
            send_resp(sock, f"gold={p.gold} buildings={p.buildings}".encode())
        else:
            send_resp(sock, b"ERR unknown opcode")
    sock.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["naive", "hardened"], default="naive")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9933)
    a = ap.parse_args()
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((a.host, a.port)); s.listen(8)
    print(f"  mock-сервер [{a.mode}] на {a.host}:{a.port}")
    while True:
        c, addr = s.accept()
        threading.Thread(target=handle, args=(c, a.mode), daemon=True).start()


if __name__ == "__main__":
    main()
