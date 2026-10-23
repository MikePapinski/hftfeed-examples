using System.Globalization;
using HFTFeed.Client;

// Your hftfeed.com login, read from environment variables so it never ends up in source control.
var email = Environment.GetEnvironmentVariable("HFTFEED_EMAIL");
var password = Environment.GetEnvironmentVariable("HFTFEED_PASSWORD");
if (string.IsNullOrEmpty(email) || string.IsNullOrEmpty(password))
{
    Console.Error.WriteLine("Set HFTFEED_EMAIL and HFTFEED_PASSWORD first.");
    return 1;
}

using var client = new HFTFeedClient(email, password);

// Symbol key -> symbol. Filled before subscribing, then only read by the tick handler.
var symbolsByKey = new Dictionary<string, HFTFeedSymbol>();

client.AutoReconnect = true;
client.OnConnectionStatus = status => Console.WriteLine($"Connection: {status}");
client.OnSubscribe = notice => Console.WriteLine(notice);
client.OnError = error => Console.Error.WriteLine($"Error: {error.Message}");
client.OnNewTick = tick =>
{
    // Runs on the client's receive thread: keep it short.
    // Console output is fine for a demo; see "Process ticks off the receive thread" for production code.
    if (!symbolsByKey.TryGetValue(tick.Symbol, out var symbol)) return;
    var format = "F" + (int)symbol.Digits;
    Console.WriteLine(
        $"{tick.EntryTimeUtc:HH:mm:ss.fff} {symbol.SymbolName,-8} " +
        $"{tick.Bid.ToString(format, CultureInfo.InvariantCulture)} / " +
        $"{tick.Ask.ToString(format, CultureInfo.InvariantCulture)}");
};

try
{
    // Signs in, connects, logs on and loads the symbol list.
    await client.StartAsync();
}
catch (HFTFeedLogoutException ex) when (ex.IsTooManySessions)
{
    Console.Error.WriteLine("This account is already connected from another program.");
    return 1;
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Could not connect: {ex.Message}");
    return 1;
}

var symbols = client.GetSymbols();
Console.WriteLine($"{symbols.Length} symbols:");
foreach (var s in symbols)
{
    Console.WriteLine($"  {s.SymbolKey,-6} {s.SymbolName,-10} {s.Digits} digits");
    symbolsByKey[s.SymbolKey] = s;
}

// Choose symbols by name, subscribe by key.
foreach (var name in new[] { "EURUSD", "XAUUSD" })
{
    var symbol = symbols.FirstOrDefault(s => s.SymbolName == name);
    if (symbol is null)
        Console.WriteLine($"{name} is not in the symbol list.");
    else
        client.Subscribe(symbol.SymbolKey);
}

// Wait for Ctrl+C.
var stopRequested = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
Console.CancelKeyPress += (_, e) =>
{
    e.Cancel = true; // keep the process alive so the client can log out
    stopRequested.TrySetResult();
};
Console.WriteLine("Streaming. Press Ctrl+C to stop.");
await stopRequested.Task;

await client.StopAsync(); // sends a FIX Logout and closes the connection
Console.WriteLine($"Stopped. {client.TPM} ticks received in the last minute.");
return 0;
