# HFTFeed examples

Working code for connecting to [HFTFeed](https://hftfeed.com/?utm_source=github&utm_medium=repo&utm_campaign=hftfeed_examples), the low-latency multi-venue market data feed over FIX 4.4 from Equinix LD4, London.

Each folder matches a tutorial on the [HFTFeed YouTube channel](https://www.youtube.com/@HFTFeed) and a page in the [docs](https://hftfeed.com/docs?utm_source=github&utm_medium=repo&utm_campaign=hftfeed_examples).

| Example | Language | What it does | Docs |
| --- | --- | --- | --- |
| [`csharp/quickstart`](csharp/quickstart) | C# (.NET 8+) | Connects with the `HFTFeed.Client` NuGet package, prints the symbol list, streams EURUSD and gold, and logs out cleanly on Ctrl+C | [.NET SDK](https://hftfeed.com/docs/dotnet?utm_source=github&utm_medium=repo&utm_campaign=hftfeed_examples) |
| [`python/hftfeed_fix.py`](python/hftfeed_fix.py) | Python 3 (standard library only) | Speaks raw FIX 4.4 over a socket, with no SDK and no FIX library: logon, symbol list, market data request, snapshots, heartbeats, clean logout | [FIX reference](https://hftfeed.com/docs/fixmsg?utm_source=github&utm_medium=repo&utm_campaign=hftfeed_examples) |

More examples (recording tick data, building candles) will land here as the tutorials ship.

## Before you run anything

- **An hftfeed.com account with an active plan or a trial.** The 24-hour trial costs $50, covers EURUSD, GBPUSD and XAUUSD over FIX, and comes off your first plan if you subscribe within 7 days. Its 24 hours start at your first FIX logon. Get it on the [Trial](https://hftfeed.com/trial?utm_source=github&utm_medium=repo&utm_campaign=hftfeed_examples) page.
- **Outbound TCP to `fix-server.hftfeed.com` on port 9030** (or 9031, which serves the same feed). Check it with `nc -vz fix-server.hftfeed.com 9030`.
- **One live session per account.** Stop any other program using the same login first.

## C# quickstart

```bash
cd csharp/quickstart
export HFTFEED_EMAIL="you@example.com"
export HFTFEED_PASSWORD="your-password"
dotnet run
```

On Windows (PowerShell):

```powershell
cd csharp/quickstart
$env:HFTFEED_EMAIL = "you@example.com"
$env:HFTFEED_PASSWORD = "your-password"
dotnet run
```

You should see `Connection: CONNECTED`, the symbol list, two `Subscribed:` notices and then one line per price update. Ticks only flow while a market is open. Press Ctrl+C to stop: the app sends a FIX Logout before it exits.

The login is read from environment variables so it never ends up in source control. The feed connection is plain TCP, so use a password you don't use anywhere else.

## Python, raw FIX 4.4

```bash
export HFTFEED_COMP_ID=C1000            # your Quote Sender Comp ID from the Connection page
export HFTFEED_USER="you@example.com"   # your hftfeed.com e-mail
export HFTFEED_PASSWORD="your-password"
python3 python/hftfeed_fix.py           # Ctrl+C logs out cleanly
```

Optional: `HFTFEED_SYMBOLS=2001,1013` (symbol keys), `HFTFEED_HEARTBEAT=30` (5–60 s), `HFTFEED_RAW=1` to print every FIX frame. No third-party packages are needed. The same messages work from any language that can open a TCP socket.

## Limits worth knowing

- Up to 64 subscriptions per session and 50 messages per second from your side.
- At most 6 new connections per minute from one IP address. The SDK keeps you under that.
- Keep `OnNewTick` short. If your application falls behind for 10 seconds, the server ends the session.

The full list is in the [FIX reference](https://hftfeed.com/docs/fixmsg?utm_source=github&utm_medium=repo&utm_campaign=hftfeed_examples#limits).

## Help

Questions about your account or connection: [hftfeed.com support](https://hftfeed.com/helpdesk/support). Include your SenderCompID and the time of the problem (UTC). Never send your password.

Bugs or improvements to these examples: open an issue here.

## License

MIT
