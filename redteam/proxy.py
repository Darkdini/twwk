#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────
#  TWWK red-team PoC · перехватывающий TCP-прокси (MITM)
#  НАЗНАЧЕНИЕ: авторизованное тестирование СВОЕГО сервера/аккаунта.
#  Доказывает находку №2 (доверяет ли сервер клиенту): прокси садится
#  между твоим клиентом и твоим сервером, пишет все кадры на диск и
#  умеет на лету подменять/повторять их (tamper()).
#
#  ⚠ Запускай ТОЛЬКО против сервера и аккаунта, которыми владеешь.
#    Не направляй на боевой шард с живыми игроками.
# ─────────────────────────────────────────────────────────────────────
import socket, threading, time, json, os, sys, argparse

# ── КОНФИГ: впиши СВОЙ сервер. По умолчанию — заглушка localhost. ─────
DEFAULT_TARGET_HOST = "127.0.0.1"   # ← адрес ТВОЕГО игрового сервера
DEFAULT_TARGET_PORT = 9933          # ← порт ТВОЕГО игрового сервера
LISTEN_HOST         = "0.0.0.0"
LISTEN_PORT         = 9933          # клиент направляешь сюда (hosts/конфиг)

REC_PATH = os.path.join(os.path.dirname(__file__), "captures")

BANNER = r"""
  TWWK MITM PoC — authorized testing only
  client → [ this proxy ] → your server     (записывает + может править трафик)
"""

def hexdump(b, width=16):
    out = []
    for i in range(0, len(b), width):
        chunk = b[i:i+width]
        hexs = " ".join(f"{x:02x}" for x in chunk)
        text = "".join(chr(x) if 32 <= x < 127 else "." for x in chunk)
        out.append(f"  {i:04x}  {hexs:<{width*3}}  {text}")
    return "\n".join(out)


def dissect(direction, data):
    """Best-effort разбор кадра. Точный сериализатор у TWWK кастомный,
    поэтому показываем первый байт как опкод + длину + hex — этого хватает,
    чтобы глазами сопоставить действие в игре с кадром на проводе."""
    if not data:
        return ""
    op = data[0]
    return f"[{direction}] len={len(data)} op?=0x{op:02x}({op})\n{hexdump(data)}"


class Tamper:
    """Точка вмешательства «врага». Верни изменённые байты или None,
    чтобы пропустить кадр без изменений. Редактируй под свой тест."""
    def __init__(self, rules):
        self.rules = rules or {}

    def __call__(self, direction, data):
        # пример: --tamper c2s:DEADBEEF:CAFEBABE заменит подстроку байт
        for d, find_hex, repl_hex in self.rules.get(direction, []):
            find, repl = bytes.fromhex(find_hex), bytes.fromhex(repl_hex)
            if find in data:
                new = data.replace(find, repl)
                print(f"  ⚠ TAMPER [{direction}] {find_hex} → {repl_hex}")
                return new
        return None


class Session:
    counter = 0

    def __init__(self, client_sock, target, tamper, record):
        Session.counter += 1
        self.id = Session.counter
        self.client = client_sock
        self.target = target
        self.tamper = tamper
        self.record = record
        self.server = None
        os.makedirs(REC_PATH, exist_ok=True)
        self.rec_file = os.path.join(REC_PATH, f"session_{self.id}.jsonl")

    def log(self, direction, data):
        print(dissect(direction, data), flush=True)
        if self.record:
            with open(self.rec_file, "a") as f:
                f.write(json.dumps({
                    "t": round(time.time(), 4),
                    "dir": direction,             # c2s | s2c
                    "hex": data.hex(),
                }) + "\n")

    def pump(self, src, dst, direction):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                self.log(direction, data)
                mutated = self.tamper(direction, data)
                dst.sendall(mutated if mutated is not None else data)
        except OSError:
            pass
        finally:
            for s in (src, dst):
                try: s.close()
                except OSError: pass

    def run(self):
        try:
            self.server = socket.create_connection(self.target, timeout=10)
            self.server.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as e:
            print(f"  ✗ session {self.id}: не подключиться к серверу {self.target}: {e}")
            self.client.close()
            return
        print(f"  ✓ session {self.id} открыта → запись в {os.path.basename(self.rec_file)}")
        a = threading.Thread(target=self.pump, args=(self.client, self.server, "c2s"), daemon=True)
        b = threading.Thread(target=self.pump, args=(self.server, self.client, "s2c"), daemon=True)
        a.start(); b.start(); a.join(); b.join()
        print(f"  · session {self.id} закрыта")


def parse_tamper(items):
    rules = {}
    for it in items or []:
        try:
            direction, find_hex, repl_hex = it.split(":")
            rules.setdefault(direction, []).append((direction, find_hex, repl_hex))
        except ValueError:
            print(f"  плохое правило --tamper: {it} (формат dir:HEXFIND:HEXREPL)")
    return rules


def main():
    ap = argparse.ArgumentParser(description="TWWK MITM PoC (authorized testing only)")
    ap.add_argument("--target-host", default=DEFAULT_TARGET_HOST)
    ap.add_argument("--target-port", type=int, default=DEFAULT_TARGET_PORT)
    ap.add_argument("--listen-host", default=LISTEN_HOST)
    ap.add_argument("--listen-port", type=int, default=LISTEN_PORT)
    ap.add_argument("--no-record", action="store_true", help="не писать кадры на диск")
    ap.add_argument("--tamper", action="append",
                    help="правило подмены dir:HEXFIND:HEXREPL, напр. c2s:0a00:0aff")
    args = ap.parse_args()

    print(BANNER)
    if (args.target_host, args.target_port) == ("127.0.0.1", 9933):
        print("  ⚠ цель = localhost:9933 (заглушка). Впиши СВОЙ сервер в КОНФИГ или через --target-host.\n")

    tamper = Tamper(parse_tamper(args.tamper))
    target = (args.target_host, args.target_port)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.listen_host, args.listen_port))
    srv.listen(16)
    print(f"  слушаю {args.listen_host}:{args.listen_port} → форвард на {target[0]}:{target[1]}")
    print("  направь игровой клиент на этот адрес и играй. Ctrl+C — стоп.\n")
    try:
        while True:
            cs, addr = srv.accept()
            print(f"  ← подключился клиент {addr[0]}:{addr[1]}")
            Session(cs, target, tamper, not args.no_record).run_in_thread()
    except KeyboardInterrupt:
        print("\n  стоп.")
    finally:
        srv.close()


# маленький помощник, чтобы не плодить кода в main
def _run_in_thread(self):
    threading.Thread(target=self.run, daemon=True).start()
Session.run_in_thread = _run_in_thread

if __name__ == "__main__":
    main()
