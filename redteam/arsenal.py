#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────
#  TWWK red-team · АРСЕНАЛ «врага» (live)
#
#  «Поменять в клиенте что угодно и отправить» — вживую, чтобы видеть,
#  чему сервер верит. Каждая команда — это то, что сделал бы атакующий
#  с модифицированным клиентом; сервер отвечает правду о себе.
#
#  ⚠ Только против СВОЕГО сервера/тест-аккаунта.
#
#  Команды:
#    login <имя>           — войти
#    state                 — спросить состояние
#    setres <N>            — НАГЛО выставить себе ресурсы = N (доверие клиенту?)
#    build                 — построить (наивный сервер примет «голый» кадр)
#    replay <N>            — повторить build N раз (анти-replay / флуд)
#    raw <hexopcode> <hex> — отправить произвольный кадр (полный контроль)
#    fuzz                  — кривые кадры (устойчивость сервера)
#    scan                  — АВТО: прогнать батарею и выдать вердикт по серверу
#
#  Пример:
#    python3 arsenal.py --host 127.0.0.1 --port 9933 scan
# ─────────────────────────────────────────────────────────────────────
import socket, struct, argparse, sys, time

OP_LOGIN, OP_BUILD, OP_SETRES, OP_GETSTATE, OP_RESP = 0x01, 0x10, 0x20, 0x30, 0x80


class Client:
    def __init__(self, host, port, quiet=False):
        self.s = socket.create_connection((host, port), timeout=6)
        self.s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.s.settimeout(3)
        self.quiet = quiet

    def send(self, opcode, payload=b""):
        self.s.sendall(bytes([opcode]) + struct.pack(">H", len(payload)) + payload)

    def recv(self):
        hdr = self._n(3)
        if not hdr: return None
        ln = struct.unpack(">H", hdr[1:3])[0]
        return self._n(ln) if ln else b""

    def _n(self, n):
        buf = b""
        while len(buf) < n:
            try: c = self.s.recv(n - len(buf))
            except socket.timeout: return None
            if not c: return None
            buf += c
        return buf

    def call(self, opcode, payload=b"", tag=""):
        self.send(opcode, payload)
        r = self.recv()
        txt = (r if r is not None else "<нет ответа>".encode()).decode("utf-8", "replace")
        if not self.quiet:
            print(f"  → {tag or hex(opcode):<22} ← {txt}")
        return txt

    def gold(self):
        r = self.call(OP_GETSTATE, tag="state", )
        try: return int(r.split("gold=")[1].split()[0])
        except Exception: return None

    def close(self): self.s.close()


def cmd_simple(c, op, payload, tag):
    c.call(op, payload, tag)

def attack_setres(c, n):
    return c.call(OP_SETRES, struct.pack(">i", n), tag=f"setres {n}")

def attack_replay(c, n):
    for i in range(n):
        c.call(OP_BUILD, b"", tag=f"build replay {i+1}/{n}")

def attack_fuzz(c):
    cases = [b"\xff", b"\x10\xff\xff" + b"A"*5, b"\x20\x00\x02\x41",
             b"\x99\x00\x00", bytes(range(0, 40))]
    survived = True
    for i, raw in enumerate(cases):
        try:
            c.s.sendall(raw)
            r = c.recv()
            print(f"  fuzz #{i} {raw[:8].hex():<18} ← {(r or b'<timeout/closed>')[:40]}")
        except OSError as e:
            print(f"  fuzz #{i} {raw[:8].hex():<18} ← СЕРВЕР ОБОРВАЛ СВЯЗЬ: {e}")
            survived = False
            break
    print("  устойчивость к мусору:", "ок" if survived else "СЕРВЕР УПАЛ/ЗАКРЫЛСЯ — DoS-риск")


# ─── АВТО-СКАНЕР: прогон батареи + вердикт по серверу ────────────────
def run_scan(host, port):
    print("\n══════════ TWWK red-team · авто-аудит доверия сервера ══════════\n")
    findings = []

    def fresh():
        c = Client(host, port, quiet=True)
        c.call(OP_LOGIN, b"redteam", tag="login")
        return c

    # 1) доверяет ли сервер клиентским ресурсам?
    print("[1] Тест: клиент сам выставляет себе ресурсы (setres 1 000 000 000)…")
    c = fresh()
    before = c.gold()
    c.call(OP_SETRES, struct.pack(">i", 1_000_000_000))
    after = c.gold(); c.close()
    if after == 1_000_000_000:
        print(f"    💀 ПРИНЯТО: золото {before} → {after}. Сервер ВЕРИТ клиенту.")
        findings.append(("Клиент задаёт ресурсы напрямую", "КРИТ",
                         "Удалить любые клиент-устанавливающие команды; ресурсы считает ТОЛЬКО сервер."))
    else:
        print(f"    ✅ отклонено (золото {before} → {after}).")

    # 2) анти-replay на действиях?
    print("\n[2] Тест: повтор одной команды build ×6 (replay)…")
    c = fresh()
    g0 = c.gold()
    for _ in range(6): c.call(OP_BUILD)
    g1 = c.gold(); c.close()
    builds = (g0 - g1) // 50 if g0 is not None and g1 is not None else 0
    if builds >= 2:
        print(f"    💀 ПРИНЯТО: повтор применён {builds} раз (золото {g0} → {g1}).")
        findings.append(("Нет анти-replay на действиях", "КРИТ",
                         "Каждой команде — возрастающий seq + nonce; повтор/расхождение отклонять."))
    else:
        print(f"    ✅ повтор отклонён.")

    # 3) подделка кадра (нет подписи)?
    print("\n[3] Тест: build с произвольным телом без подписи…")
    c = fresh()
    r = c.call(OP_BUILD, b"\x00\x00\x00\x01forged"); c.close()
    if r.startswith("OK"):
        print(f"    💀 ПРИНЯТО: «{r}». Сервер не проверяет целостность кадра.")
        findings.append(("Нет проверки целостности (MAC)", "ВЫС",
                         "Подписывать команды HMAC на сессионном ключе; неподписанное — отбрасывать."))
    else:
        print(f"    ✅ отклонено: «{r}».")

    # 4) устойчивость к мусору
    print("\n[4] Тест: фаззинг кривыми кадрами…")
    try:
        c = fresh(); attack_fuzz(c); c.close()
    except OSError as e:
        print(f"    СЕРВЕР УПАЛ во время фаззинга: {e}")
        findings.append(("Падение на некорректных кадрах", "ВЫС",
                         "Жёстко валидировать длины/типы; не глотать исключения молча; рейт-лимит."))

    # ── вердикт ──
    print("\n──────────────────── ВЕРДИКТ ────────────────────")
    if not findings:
        print("  ✅ Сервер устоял по всем тестам. Так и держать.")
    else:
        print(f"  Найдено слабостей: {len(findings)}\n")
        for i, (name, sev, fix) in enumerate(findings, 1):
            print(f"  {i}. [{sev}] {name}\n     → чинить: {fix}\n")
    print("  Подробный чеклист — redteam/SERVER_HARDENING.md")
    print("═══════════════════════════════════════════════════\n")
    return findings


# ─── ЖИВОЙ РЕЖИМ: меняй и шли что хочешь руками ──────────────────────
def run_repl(host, port):
    c = Client(host, port)
    print("  живой режим. команды: login <имя> | state | setres <N> | build |")
    print("               replay <N> | raw <hexOp> <hex> | quit")
    while True:
        try:
            line = input("  враг> ").strip()
        except (EOFError, KeyboardInterrupt):
            print(); break
        if not line: continue
        parts = line.split()
        cmd, args = parts[0], parts[1:]
        try:
            if cmd in ("quit", "exit", "q"): break
            elif cmd == "login":  c.call(OP_LOGIN, (args[0] if args else "redteam").encode(), tag="login")
            elif cmd == "state":  c.call(OP_GETSTATE, tag="state")
            elif cmd == "setres": attack_setres(c, int(args[0]))
            elif cmd == "build":  c.call(OP_BUILD, tag="build")
            elif cmd == "replay": attack_replay(c, int(args[0]) if args else 5)
            elif cmd == "raw":    c.call(int(args[0],16), bytes.fromhex(args[1]) if len(args)>1 else b"", tag=f"raw {args[0]}")
            else: print("  ? неизвестная команда")
        except (IndexError, ValueError) as e:
            print(f"  плохие аргументы: {e}")
    c.close()


def main():
    ap = argparse.ArgumentParser(description="TWWK red-team arsenal (authorized testing only)")
    ap.add_argument("--host", required=True)
    ap.add_argument("--port", type=int, required=True)
    sub = ap.add_argument_group("команда")
    ap.add_argument("cmd", choices=["login","state","setres","build","replay","raw","fuzz","scan","repl"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()

    if a.cmd == "scan":
        run_scan(a.host, a.port); return
    if a.cmd == "repl":
        run_repl(a.host, a.port); return

    c = Client(a.host, a.port)
    if   a.cmd == "login":  c.call(OP_LOGIN, (a.args[0] if a.args else "redteam").encode(), tag="login")
    elif a.cmd == "state":  c.call(OP_GETSTATE, tag="state")
    elif a.cmd == "setres": attack_setres(c, int(a.args[0]))
    elif a.cmd == "build":  c.call(OP_BUILD, tag="build")
    elif a.cmd == "replay": attack_replay(c, int(a.args[0]) if a.args else 5)
    elif a.cmd == "fuzz":   attack_fuzz(c)
    elif a.cmd == "raw":
        op = int(a.args[0], 16); body = bytes.fromhex(a.args[1]) if len(a.args) > 1 else b""
        c.call(op, body, tag=f"raw {op:#x}")
    c.close()


if __name__ == "__main__":
    main()
