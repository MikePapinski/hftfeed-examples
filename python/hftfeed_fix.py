#!/usr/bin/env python3
"""HFTfeed market data over raw FIX 4.4: a minimal client, standard library only.

    export HFTFEED_COMP_ID=C1234 HFTFEED_USER=you@example.com HFTFEED_PASSWORD=...
    python3 hftfeed_fix.py            # Ctrl+C logs out cleanly

Limits (docs): one live session per account, up to 64 subscriptions, at most 50 messages/s
from you, and keep reading the socket the whole time or the server logs you out (slow consumer).
"""
import datetime, os, select, socket, sys, time

SOH = "\x01"                       # FIX field separator (shown as | in the docs)
HOST = os.environ.get("HFTFEED_HOST", "fix-server.hftfeed.com")
PORT = int(os.environ.get("HFTFEED_PORT", "9030"))
COMP_ID = os.environ["HFTFEED_COMP_ID"]          # your Quote Sender Comp ID
USER = os.environ["HFTFEED_USER"]                # your hftfeed.com email
PASSWORD = os.environ["HFTFEED_PASSWORD"]        # your hftfeed.com password
SYMBOLS = os.environ.get("HFTFEED_SYMBOLS", "2001,1013").split(",")  # XAUUSD, EURUSD
HEARTBEAT = int(os.environ.get("HFTFEED_HEARTBEAT", "30"))           # 5..60 s
SHOW_RAW = os.environ.get("HFTFEED_RAW") == "1"                      # print every frame


def utc_now():
    """SendingTime (52): yyyyMMdd-HH:mm:ss.fff in UTC."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H:%M:%S.%f")[:-3]


class FixClient:
    def __init__(self):
        self.sock = socket.create_connection((HOST, PORT), timeout=10)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.seq = 1               # our MsgSeqNum (34); 141=Y resets it to 1 at every logon
        self.inbox = b""           # bytes received but not yet parsed
        self.last_sent = time.monotonic()
        self.symbols = {}          # "2001" -> ("XAUUSD", 2)

    # ---- encoding ------------------------------------------------------
    def send(self, msg_type, fields=()):
        header = [(35, msg_type), (34, self.seq), (49, COMP_ID), (50, "QUOTE"),
                  (52, utc_now()), (56, "FixServer"), (57, "QUOTE")]
        body = "".join(f"{tag}={value}{SOH}" for tag, value in header + list(fields))
        head = f"8=FIX.4.4{SOH}9={len(body)}{SOH}"            # BodyLength = bytes after 9=..| up to 10=
        checksum = sum((head + body).encode("ascii")) % 256    # CheckSum = byte sum mod 256, 3 digits
        frame = f"{head}{body}10={checksum:03d}{SOH}"
        self.sock.sendall(frame.encode("ascii"))
        self.seq += 1
        self.last_sent = time.monotonic()
        if SHOW_RAW:
            print("->", frame.replace(SOH, "|"))

    # ---- decoding ------------------------------------------------------
    def read_messages(self):
        """Yield every complete frame in the socket buffer as a list of (tag, value) pairs."""
        data = self.sock.recv(65536)
        if not data:
            raise ConnectionError("server closed the connection")
        self.inbox += data
        while True:
            start = self.inbox.find(b"9=")
            end_of_9 = self.inbox.find(b"\x01", start)
            if start < 0 or end_of_9 < 0:
                return
            frame_end = end_of_9 + 1 + int(self.inbox[start + 2:end_of_9]) + 7   # body + "10=nnn|"
            if len(self.inbox) < frame_end:
                return                                                          # wait for the rest
            frame, self.inbox = self.inbox[:frame_end], self.inbox[frame_end:]
            if sum(frame[:-7]) % 256 != int(frame[-4:-1]):
                raise ValueError("bad checksum")
            if SHOW_RAW:
                print("<-", frame.decode("ascii").replace(SOH, "|"))
            yield [tuple(f.split("=", 1)) for f in frame.decode("ascii").split(SOH)[:-1]]

    # ---- session -------------------------------------------------------
    def logon(self):
        self.send("A", [(98, 0), (108, HEARTBEAT), (141, "Y"), (553, USER), (554, PASSWORD)])

    def request_symbols(self):
        self.send("x", [(320, "symbols-1"), (559, 0)])

    def subscribe(self, keys):
        assert len(keys) <= 64, "a session can hold up to 64 subscriptions"
        self.send("V", [(262, "md-1"), (263, 1), (264, 1), (267, 2), (269, 0), (269, 1),
                        (146, len(keys))] + [(55, k) for k in keys])

    def logout(self):
        self.send("5")

    def handle(self, msg):
        fields = dict(msg)                     # last value wins; groups are walked in order below
        msg_type = fields["35"]
        if msg_type == "A":
            print(f"logged on, heartbeat {fields['108']} s")
            self.request_symbols()
        elif msg_type == "y":
            for i, (tag, value) in enumerate(msg):
                if tag == "55":                # each symbol: 55 key, 1007 name, 1008 digits
                    self.symbols[value] = (msg[i + 1][1], int(msg[i + 2][1]))
            print(f"{len(self.symbols)} symbols, subscribing to {', '.join(SYMBOLS)}")
            self.subscribe(SYMBOLS)
        elif msg_type in ("W", "X"):           # W = full snapshot; X (incremental) is never sent but parses the same
            self.print_quote(msg)
        elif msg_type == "1":                  # TestRequest: answer with a Heartbeat echoing 112
            self.send("0", [(112, fields["112"])])
        elif msg_type in ("Y", "3"):
            print("rejected:", fields.get("58"))
        elif msg_type == "5":
            print("logout:", fields.get("58", ""))
            return False
        return True                            # 0 Heartbeat needs no answer

    def print_quote(self, msg):
        symbol, side, quote = None, None, {}
        for tag, value in msg:
            if tag == "55":
                symbol = value
            elif tag == "269":
                side = "bid" if value == "0" else "ask"
            elif tag == "270":
                quote[side] = value
            elif tag == "273":
                quote["time"] = value
        name = self.symbols.get(symbol, (symbol, 0))[0]
        print(f"{quote.get('time', ''):>12}  {name:<7} bid {quote.get('bid', '-'):>10}  ask {quote.get('ask', '-'):>10}")

    def run(self):
        self.logon()
        logged_out = False
        try:
            while True:                        # read continuously; never stop reading while connected
                ready, _, _ = select.select([self.sock], [], [], 0.5)
                if ready:
                    for msg in self.read_messages():
                        if not self.handle(msg):
                            return
                if time.monotonic() - self.last_sent >= HEARTBEAT:
                    self.send("0")             # Heartbeat when we have been quiet for HeartBtInt
        except KeyboardInterrupt:
            print("\nlogging out...")
            self.logout()
            deadline = time.monotonic() + 3
            try:                               # wait for the server's Logout (quotes may still arrive first)
                while not logged_out and time.monotonic() < deadline:
                    if select.select([self.sock], [], [], 0.2)[0]:
                        for msg in self.read_messages():
                            if dict(msg)["35"] == "5":
                                print("logout:", dict(msg).get("58", ""))
                                logged_out = True
            except ConnectionError:
                pass                           # server closed the socket: also fine
        finally:
            self.sock.close()


if __name__ == "__main__":
    FixClient().run()
